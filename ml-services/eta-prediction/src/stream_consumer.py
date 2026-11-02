import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

from .eta_publisher import create_producer, publish_dlq, publish_prediction
from .h2_predict import predict_h2
from .seed_routes import load_seed_routes

log = logging.getLogger(__name__)

INPUT_TOPIC = "supplierportal.shipment.dispatched"
OUTPUT_TOPIC = "eta.shipment.predicted"
DLQ_TOPIC = "eta.shipment.dispatched.dlq"

CONSUMER_GROUP = "eta-prediction-v1"


def load_settings(env=None):
    env = os.environ if env is None else env

    return {
        "bootstrap_servers": env.get(
            "KAFKA_BOOTSTRAP_SERVERS",
            "localhost:9092",
        ),
        "group_id": env.get(
            "KAFKA_GROUP_ID",
            CONSUMER_GROUP,
        ),
        "input_topic": env.get(
            "KAFKA_INPUT_TOPIC",
            INPUT_TOPIC,
        ),
        "output_topic": env.get(
            "KAFKA_OUTPUT_TOPIC",
            OUTPUT_TOPIC,
        ),
        "dlq_topic": env.get(
            "KAFKA_DLQ_TOPIC",
            DLQ_TOPIC,
        ),
    }
REQUIRED_EVENT_FIELDS = (
    "event_id",
    "event_type",
    "event_version",
    "occurred_at",
    "producer",
    "payload",
)

REQUIRED_PAYLOAD_FIELDS = (
    "shipment_id",
    "po_number",
    "supplier_id",
    "origin",
    "destination_warehouse",
    "carrier",
    "dispatched_at",
)


def validate_event(event):
    if not isinstance(event, dict):
        raise ValueError("Event must be a JSON object.")

    missing = [field for field in REQUIRED_EVENT_FIELDS if field not in event]
    if missing:
        raise ValueError(f"Missing event fields: {missing}")

    if event["event_type"] != INPUT_TOPIC:
        raise ValueError(f"Unexpected event_type: {event['event_type']!r}")

    if event["event_version"] != 1:
        raise ValueError(f"Unsupported event_version: {event['event_version']!r}")

    if event["producer"] != "supplier-portal":
        raise ValueError(f"Unexpected producer: {event['producer']!r}")

    try:
        event_uuid = UUID(event["event_id"])
        if event_uuid.version != 4:
            raise ValueError
    except (ValueError, AttributeError):
        raise ValueError("Invalid event_id: expected UUID v4.")

    try:
        datetime.fromisoformat(event["occurred_at"].replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise ValueError("Invalid occurred_at: expected an ISO 8601 datetime.")

    payload = event["payload"]

    if not isinstance(payload, dict):
        raise ValueError("Event payload must be an object.")

    missing = [field for field in REQUIRED_PAYLOAD_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"Missing payload fields: {missing}")

    patterns = {
        "shipment_id": r"^SHP-[0-9]{4}-[0-9]{6}$",
        "po_number": r"^PO-[0-9]{4}-[0-9]{6}$",
        "supplier_id": r"^SUP-[0-9]{5}$",
        "destination_warehouse": r"^WH-[A-Z]{3}-[0-9]{2}$",
    }

    for field, pattern in patterns.items():
        if not isinstance(payload[field], str) or not re.fullmatch(
            pattern, payload[field]
        ):
            raise ValueError(f"Invalid {field} format.")

    for field in ("origin", "carrier"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError(f"{field} must be a non-empty string.")

    try:
        datetime.fromisoformat(payload["dispatched_at"].replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise ValueError(
            "Invalid dispatched_at: expected an ISO 8601 datetime."
        )

    return event

def build_prediction_event(event, prediction):
    """Build the eta.shipment.predicted event from a dispatched shipment."""

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "event_id": str(uuid4()),
        "event_type": OUTPUT_TOPIC,
        "event_version": 1,
        "occurred_at": now,
        "producer": "eta-prediction",
        "trace_id": event.get("trace_id"),
        "payload": {
            "shipment_id": event["payload"]["shipment_id"],
            "po_number": event["payload"]["po_number"],
            **prediction,
            "model_version": "eta_seed_routes/1",
            "predicted_at": now,
        },
    }

class EventDeduplicator:
    """Keep track of event_ids already processed by this consumer."""

    def __init__(self):
        self._processed = set()

    def is_duplicate(self, event_id):
        return event_id in self._processed

    def mark_processed(self, event_id):
        self._processed.add(event_id)

def run(settings):
    from confluent_kafka import Consumer, KafkaException

    consumer = Consumer(
        {
            "bootstrap.servers": settings["bootstrap_servers"],
            "group.id": settings["group_id"],
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )

    consumer.subscribe([settings["input_topic"]])
    producer = create_producer()
    deduplicator = EventDeduplicator()

    log.info(
        "ETA consumer started: topic=%s group=%s",
        settings["input_topic"],
        settings["group_id"],
    )

    try:
        while True:
            message = consumer.poll(1.0)

            if message is None:
                continue

            if message.error():
                raise KafkaException(message.error())

            try:
                event = json.loads(message.value().decode("utf-8"))
                validate_event(event)

            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                log.warning(
                    "Invalid event at %s[%d]@%d: %s",
                    message.topic(),
                    message.partition(),
                    message.offset(),
                    exc,
                )

                raw_message = message.value().decode("utf-8", errors="replace")

                publish_dlq(
                    producer=producer,
                    raw_message=raw_message,
                    error_reason=str(exc),
                    topic=message.topic(),
                    consumer_group=settings["group_id"],
                    partition=message.partition(),
                    offset=message.offset(),
                )

                consumer.commit(
                    message=message,
                    asynchronous=False,
                )
                continue

            event_id = event["event_id"]

            if deduplicator.is_duplicate(event_id):
                log.info("Skipping duplicate event_id=%s", event_id)
                consumer.commit(
                    message=message,
                    asynchronous=False,
                )
                continue

            log.info("Received event_id=%s", event_id)
            start_time = time.perf_counter()
            routes = load_seed_routes()

            prediction = predict_h2(
                event["payload"],
                routes,
            )
            prediction_event = build_prediction_event(
                event,
                prediction,
            )

            publish_prediction(producer, prediction_event)
            deduplicator.mark_processed(event_id)

            latency_ms = (time.perf_counter() - start_time) * 1000

            log.info(
                "ETA event latency: event_id=%s latency_ms=%.2f",
                event_id,
                latency_ms,
            )

            consumer.commit(
                message=message,
                asynchronous=False,
            )
            log.info(
                "ETA prediction completed for event_id=%s: %s",
                event_id,
                prediction,
            )

        

    finally:
        consumer.close()