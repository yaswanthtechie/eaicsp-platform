import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from kafka import KafkaProducer

KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "localhost:9092",
)

EVENT_VERSION = 1
PRODUCER_NAME = "platform-service"


def build_event(
    event_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Build the standard EAICSP event envelope.
    """

    if not event_type:
        raise ValueError(
            "event_type must not be empty"
        )

    if not isinstance(payload, dict):
        raise TypeError(
            "payload must be a dictionary"
        )

    return {
        "id": str(uuid.uuid4()),
        "event_type": event_type,
        "event_version": EVENT_VERSION,
        "occurred_at": (
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        ),
        "producer": PRODUCER_NAME,
        "payload": payload,
    }


def _create_producer() -> KafkaProducer:
    """
    Create a Kafka producer lazily.
    """

    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda value: json.dumps(
            value
        ).encode("utf-8"),
    )


def publish_event(
    event_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Publish an event to Kafka.

    The Kafka topic is the same as event_type.

    Example:

        publish_event(
            "platform.user.locked",
            {"user_id": 123},
        )
    """

    event = build_event(
        event_type=event_type,
        payload=payload,
    )

    producer = _create_producer()

    try:
        producer.send(
            event_type,
            value=event,
        ).get(timeout=10)

        producer.flush()

    finally:
        producer.close()

    return event