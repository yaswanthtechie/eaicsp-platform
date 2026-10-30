"""Kafka event sink for live dashboard updates."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

import clickhouse_connect
from kafka import KafkaConsumer, KafkaProducer

LOGGER = logging.getLogger(__name__)

GOODS_RECEIVED = "inventory.goods.received"
ETA_PREDICTED = "eta.shipment.predicted"
SUPPORTED_EVENTS = {GOODS_RECEIVED, ETA_PREDICTED}


def _parse_time(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def validate_event(event):
    """Validate the fields required by the versioned event contracts."""
    if not isinstance(event, dict):
        raise ValueError("event must be a JSON object")

    event_type = event.get("event_type")
    if event_type not in SUPPORTED_EVENTS:
        raise ValueError("unsupported event_type")
    if event.get("event_version") != 1:
        raise ValueError("unsupported event_version")

    try:
        UUID(event["event_id"])
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise ValueError("invalid event_id") from exc

    _parse_time(event.get("occurred_at"))
    payload = event.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    if event_type == GOODS_RECEIVED:
        if event.get("producer") != "inventory-service":
            raise ValueError("invalid goods-received producer")
        patterns = {
            "receipt_id": r"GR-\d{4}-\d{6}",
            "po_id": r"PO-\d{4}-\d{6}",
            "supplier_id": r"SUP-\d{5}",
            "warehouse_id": r"WH-[A-Z]{3}-\d{2}",
        }
        for key, pattern in patterns.items():
            if not isinstance(payload.get(key), str) or not re.fullmatch(
                pattern, payload[key]
            ):
                raise ValueError(f"invalid {key}")
        if payload.get("status") != "received":
            raise ValueError("status must be received")
        if not isinstance(payload.get("received_by"), str) or not payload["received_by"].strip():
            raise ValueError("received_by is required")
        _parse_time(payload.get("received_at"))
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("items must be a non-empty list")
        for item in items:
            if not isinstance(item, dict) or not re.fullmatch(
                r"SKU-\d{6}", str(item.get("sku_id", ""))
            ):
                raise ValueError("invalid item sku_id")
            quantity = item.get("quantity_received")
            if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
                raise ValueError("quantity_received must be a positive integer")
            if "unit_cost" in item and (
                isinstance(item["unit_cost"], bool)
                or not isinstance(item["unit_cost"], (int, float))
                or item["unit_cost"] < 0
            ):
                raise ValueError("unit_cost must be non-negative")
    else:
        if event.get("producer") != "eta-prediction":
            raise ValueError("invalid ETA producer")
        try:
            if UUID(event["event_id"]).version != 4:
                raise ValueError("ETA event_id must be UUID v4")
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise ValueError("ETA event_id must be UUID v4") from exc
        if not re.fullmatch(r"SHP-\d{4}-\d{6}", str(payload.get("shipment_id", ""))):
            raise ValueError("invalid shipment_id")
        if not re.fullmatch(r"PO-\d{4}-\d{6}", str(payload.get("po_number", ""))):
            raise ValueError("invalid po_number")
        for key in ("eta_days", "confidence_low", "confidence_high"):
            value = payload.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"{key} must be non-negative")
        if payload["confidence_low"] > payload["confidence_high"]:
            raise ValueError("confidence_low exceeds confidence_high")
        if not isinstance(payload.get("model_version"), str) or not payload["model_version"].strip():
            raise ValueError("model_version is required")
        _parse_time(payload.get("predicted_at"))

    return event


class ClickHouseEventSink:
    """Process one Kafka message at a time; commit only after durable handling."""

    def __init__(self, consumer, producer, client, database="analytics"):
        self.consumer = consumer
        self.producer = producer
        self.client = client
        self.database = database

    def ensure_schema(self):
        self.client.command(f"""
            CREATE TABLE IF NOT EXISTS {self.database}.dashboard_event_sink_processed
            (
                event_id String,
                event_type String,
                processed_at DateTime64(3, 'UTC'),
                version DateTime64(3, 'UTC')
            )
            ENGINE = ReplacingMergeTree(version)
            ORDER BY event_id
        """)
        self.client.command(f"""
            CREATE TABLE IF NOT EXISTS {self.database}.shipment_eta_predictions
            (
                event_id String,
                shipment_id String,
                po_number String,
                eta_days Float64,
                confidence_low Float64,
                confidence_high Float64,
                model_version String,
                predicted_at DateTime64(3, 'UTC'),
                version DateTime64(3, 'UTC')
            )
            ENGINE = ReplacingMergeTree(version)
            ORDER BY shipment_id
        """)

    def _already_processed(self, event_id):
        result = self.client.query(
            f"""SELECT event_id
                FROM {self.database}.dashboard_event_sink_processed FINAL
                WHERE event_id = {{event_id:String}}""",
            parameters={"event_id": event_id},
        )
        return bool(result.result_rows)

    def _insert(self, table, rows, columns):
        self.client.insert(
            f"{self.database}.{table}", rows, column_names=columns
        )

    def _write_goods_received(self, event):
        payload = event["payload"]
        received_at = _parse_time(payload["received_at"]).replace(tzinfo=None)
        version = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = [
            (
                payload["receipt_id"],
                payload["po_id"],
                item["sku_id"],
                payload["warehouse_id"],
                item["quantity_received"],
                received_at,
                version,
            )
            for item in payload["items"]
        ]
        self._insert(
            "goods_receipt_lines",
            rows,
            [
                "receipt_id", "po_id", "sku_id", "warehouse_id",
                "quantity_received", "received_at", "version",
            ],
        )

    def _write_eta(self, event):
        payload = event["payload"]
        predicted_at = _parse_time(payload["predicted_at"])
        version = predicted_at.replace(tzinfo=None)
        self._insert(
            "shipment_eta_predictions",
            [(
                event["event_id"],
                payload["shipment_id"],
                payload["po_number"],
                float(payload["eta_days"]),
                float(payload["confidence_low"]),
                float(payload["confidence_high"]),
                payload["model_version"],
                version,
                version,
            )],
            [
                "event_id", "shipment_id", "po_number", "eta_days",
                "confidence_low", "confidence_high", "model_version",
                "predicted_at", "version",
            ],
        )

        # Preserve existing delivery fields when updating a known shipment.
        result = self.client.query(
            f"""SELECT shipment_id, po_id, supplier_id, warehouse_id, carrier,
                       dispatched_at, predicted_eta, delivered_at, on_time,
                       delay_hours, version
                FROM {self.database}.transport_performance FINAL
                WHERE shipment_id = {{shipment_id:String}}""",
            parameters={"shipment_id": payload["shipment_id"]},
        )
        if not result.result_rows:
            LOGGER.warning(
                "No transport_performance row for %s; predicted_eta not updated",
                payload["shipment_id"],
            )
            return

        current = list(result.result_rows[0])
        dispatched_at = current[5]
        if dispatched_at.tzinfo is None:
            dispatched_at = dispatched_at.replace(tzinfo=timezone.utc)
        eta = dispatched_at + timedelta(days=float(payload["eta_days"]))
        current[6] = eta.astimezone(timezone.utc).replace(tzinfo=None)
        current[10] = version
        self._insert(
            "transport_performance",
            [tuple(current)],
            [
                "shipment_id", "po_id", "supplier_id", "warehouse_id",
                "carrier", "dispatched_at", "predicted_eta", "delivered_at",
                "on_time", "delay_hours", "version",
            ],
        )

    def _dead_letter(self, message, reason, raw):
        source_topic = message.topic
        topic = f"{source_topic}.dlq"
        record = {
            "source_topic": source_topic,
            "source_partition": message.partition,
            "source_offset": message.offset,
            "error": str(reason),
            "original_value": raw.decode("utf-8", errors="replace")
            if isinstance(raw, bytes) else str(raw),
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        # A failed send raises; the Kafka offset must not be committed.
        self.producer.send(topic, value=record).get(timeout=10)
        self.consumer.commit()
        LOGGER.warning("Sent invalid event to %s: %s", topic, reason)

    def process_message(self, message):
        raw = message.value
        try:
            event = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            validate_event(event)
        except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._dead_letter(message, exc, raw)
            return "dead_letter"

        event_id = event["event_id"]
        if self._already_processed(event_id):
            self.consumer.commit()
            return "duplicate"

        # Never commit if any ClickHouse write fails. Redelivery is safe:
        # goods rows are keyed by receipt/SKU and ETA rows by shipment.
        if event["event_type"] == GOODS_RECEIVED:
            self._write_goods_received(event)
        else:
            self._write_eta(event)

        processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self._insert(
            "dashboard_event_sink_processed",
            [(event_id, event["event_type"], processed_at, processed_at)],
            ["event_id", "event_type", "processed_at", "version"],
        )
        self.consumer.commit()
        return "processed"


def main():
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092").split(",")
    database = os.getenv("CLICKHOUSE_DATABASE", "analytics")
    consumer = KafkaConsumer(
        GOODS_RECEIVED,
        ETA_PREDICTED,
        bootstrap_servers=servers,
        group_id=os.getenv(
            "CLICKHOUSE_EVENT_SINK_GROUP", "dashboard-clickhouse-event-sink"
        ),
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        max_poll_records=1,
    )
    producer = KafkaProducer(
        bootstrap_servers=servers,
        acks="all",
        retries=3,
        value_serializer=lambda value: json.dumps(
            value, separators=(",", ":")
        ).encode("utf-8"),
    )
    password = os.getenv("CLICKHOUSE_PASSWORD")
    if not password:
        raise ValueError("CLICKHOUSE_PASSWORD must be set.")

    client = clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=password,
        database=database,
        connect_timeout=5,
    )
    sink = ClickHouseEventSink(consumer, producer, client, database)
    sink.ensure_schema()
    LOGGER.info("Live event sink started for %s", sorted(SUPPORTED_EVENTS))
    try:
        for message in consumer:
            sink.process_message(message)
    finally:
        consumer.close()
        producer.flush(timeout=10)
        producer.close()
        client.close()


if __name__ == "__main__":
    main()







