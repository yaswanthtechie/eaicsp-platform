import json
import logging
import os
import re
import time
from collections import OrderedDict
from datetime import datetime, timezone
from uuid import UUID, uuid4

from .eta_publisher import create_producer, publish_dlq, publish_prediction
from .h2_predict import load_h2_artifacts, predict_h2
from .paths import SEED_SAMPLES_DIR
from .seed_routes import load_seed_routes

log = logging.getLogger(__name__)

INPUT_TOPIC = "supplierportal.shipment.dispatched"
OUTPUT_TOPIC = "eta.shipment.predicted"
DLQ_TOPIC = f"{INPUT_TOPIC}.dlq"

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
        "seed_dir": env.get(
            "ETA_SEED_DIR",
            str(SEED_SAMPLES_DIR),
        ),
        "model_version": env.get(
            "ETA_MODEL_VERSION",
            "eta_seed_routes/1",
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
def _parse_aware_datetime(value, field):
    """Parse an ISO 8601 datetime and require a timezone (the contract's date-time format)."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise ValueError(f"Invalid {field}: expected an ISO 8601 datetime.")
    if parsed.tzinfo is None:
        raise ValueError(
            f"Invalid {field}: a timezone is required, "
            "e.g. 2026-10-15T06:30:00Z."
        )
    return parsed

def validate_event(event):
    if not isinstance(event, dict):
        raise ValueError("Event must be a JSON object.")

    missing = [field for field in REQUIRED_EVENT_FIELDS if field not in event]
    if missing:
        raise ValueError(f"Missing event fields: {missing}")

    if event["event_type"] != INPUT_TOPIC:
        raise ValueError(f"Unexpected event_type: {event['event_type']!r}")

    if event["event_version"] != 1:
        raise ValueError(
            f"Unsupported event_version: {event['event_version']!r}"
        )

    if event["producer"] != "supplier-portal":
        raise ValueError(f"Unexpected producer: {event['producer']!r}")

    try:
        event_uuid = UUID(event["event_id"])
        if event_uuid.version != 4:
            raise ValueError
    except (ValueError, AttributeError):
        raise ValueError("Invalid event_id: expected UUID v4.")

    _parse_aware_datetime(event["occurred_at"], "occurred_at")

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
            pattern,
            payload[field],
        ):
            raise ValueError(f"Invalid {field} format.")

    for field in ("origin", "carrier"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError(f"{field} must be a non-empty string.")

    _parse_aware_datetime(payload["dispatched_at"], "dispatched_at")

    return event

def build_prediction_event(event, prediction, model_version):
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
            "model_version": model_version,
            "predicted_at": now,
        },
    }


class EventDeduplicator:
    """Remember the last max_size processed event_ids (LRU)."""

    def __init__(self, max_size=10_000):
        self._processed = OrderedDict()
        self._max_size = max_size

    def is_duplicate(self, event_id):
        if event_id in self._processed:
            self._processed.move_to_end(event_id)
            return True
        return False

    def mark_processed(self, event_id):
        self._processed[event_id] = None
        self._processed.move_to_end(event_id)

        if len(self._processed) > self._max_size:
            self._processed.popitem(last=False)


def run(settings):
    from confluent_kafka import Consumer, KafkaException

    # Fail at startup, not on the first message, if data or model is missing.
    routes = load_seed_routes(settings["seed_dir"])
    load_h2_artifacts()

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

    def send_to_dlq(message, reason):
        raw_message = (message.value() or b"").decode(
            "utf-8",
            errors="replace",
        )

        publish_dlq(
            producer,
            dlq_topic=settings["dlq_topic"],
            raw_message=raw_message,
            error_reason=reason,
            topic=message.topic(),
            consumer_group=settings["group_id"],
            partition=message.partition(),
            offset=message.offset(),
        )

        consumer.commit(
            message=message,
            asynchronous=False,
        )

    try:
        while True:
            message = consumer.poll(1.0)

            if message is None:
                continue

            if message.error():
                err = message.error()

                if err.fatal():
                    raise KafkaException(err)

                log.warning("Kafka error, continuing: %s", err)
                continue

            start_time = time.perf_counter()

            # 1. Parse and validate. Bad input -> DLQ, commit, move on.
            try:
                if message.value() is None:
                    raise ValueError("Empty message value (tombstone).")

                event = json.loads(
                    message.value().decode("utf-8")
                )
                validate_event(event)

            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                log.warning(
                    "Invalid event at %s[%d]@%d: %s",
                    message.topic(),
                    message.partition(),
                    message.offset(),
                    exc,
                )
                send_to_dlq(message, str(exc))
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

            # 2. Predict. A valid event we cannot predict -> DLQ.
            try:
                prediction = predict_h2(
                    event["payload"],
                    routes,
                )
            except (ValueError, KeyError) as exc:
                log.warning(
                    "Cannot predict ETA for event_id=%s: %s",
                    event_id,
                    exc,
                )
                send_to_dlq(
                    message,
                    f"Prediction failed: {exc}",
                )
                continue

            prediction_event = build_prediction_event(
                event,
                prediction,
                settings["model_version"],
            )

            # 3. Publish. Broker failure raises and prevents offset commit.
            publish_prediction(
                producer,
                prediction_event,
                settings["output_topic"],
            )

            deduplicator.mark_processed(event_id)

            consumer.commit(
                message=message,
                asynchronous=False,
            )

            processing_ms = (
                time.perf_counter() - start_time
            ) * 1000

            occurred_at = datetime.fromisoformat(
                event["occurred_at"].replace("Z", "+00:00")
            )

            end_to_end_ms = (
                datetime.now(timezone.utc) - occurred_at
            ).total_seconds() * 1000

            log.info(
                "ETA event latency: event_id=%s "
                "processing_ms=%.2f end_to_end_ms=%.2f",
                event_id,
                processing_ms,
                end_to_end_ms,
            )

            log.info(
                "ETA prediction completed for event_id=%s: %s",
                event_id,
                prediction,
            )

    finally:
        producer.flush(10)
        consumer.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run(load_settings())
