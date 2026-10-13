"""
Shared Kafka event publisher for EAICSP services.

    publish_event("platform.user.locked", {"user_id": 123})

* Builds the standard envelope:
  event_id, event_type, event_version, occurred_at (UTC), producer, payload.
* Topic name == event_type.
* NEVER raises. If Kafka is down or slow, the failure is logged and
  publish_event returns None within about PUBLISH_TIMEOUT_SECONDS, so a
  business action (for example an account lock) is never blocked or
  undone by Kafka.
* Delivery is best-effort (at most once): an event that fails to publish
  is logged, not retried.
"""

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from kafka import KafkaProducer

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "localhost:9092",
)

# Upper bound on how long publish_event may block the caller.
PUBLISH_TIMEOUT_SECONDS = float(
    os.getenv("KAFKA_PUBLISH_TIMEOUT_SECONDS", "2")
)

EVENT_VERSION = 1
PRODUCER_NAME = "platform-service"

_producer: KafkaProducer | None = None
_producer_lock = threading.Lock()


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
        "event_id": str(uuid.uuid4()),
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
    Create the Kafka producer.

    api_version is set explicitly so creating the producer does not try to
    contact Kafka. max_block_ms caps how long send() waits when Kafka is
    unreachable.
    """
    timeout_ms = int(PUBLISH_TIMEOUT_SECONDS * 1000)

    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        api_version=(3, 9),
        max_block_ms=timeout_ms,
        request_timeout_ms=timeout_ms,
        retries=0,
        value_serializer=lambda value: json.dumps(
            value
        ).encode("utf-8"),
    )


def _get_producer() -> KafkaProducer:
    """
    Return one shared producer, created on first use.

    Creating a producer opens network connections, so it is reused for
    every event instead of being created per call.
    """
    global _producer

    with _producer_lock:
        if _producer is None:
            _producer = _create_producer()

        return _producer


def _reset_producer() -> None:
    """Drop a broken producer so the next call creates a fresh one."""
    global _producer

    with _producer_lock:
        if _producer is not None:
            try:
                _producer.close(timeout=1)
            except Exception:  # noqa: BLE001
                pass

        _producer = None


def publish_event(
    event_type: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Publish an event to Kafka. The topic is the same as event_type.

    Returns the published envelope, or None if it could not be published.
    Never raises for Kafka problems (it still raises ValueError/TypeError
    for a programming mistake such as an empty event_type).
    """

    event = build_event(
        event_type=event_type,
        payload=payload,
    )

    try:
        _get_producer().send(
            event_type,
            value=event,
        ).get(timeout=PUBLISH_TIMEOUT_SECONDS)

        return event

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Kafka publish failed | event_type=%s | event_id=%s | error=%s",
            event_type,
            event["event_id"],
            type(exc).__name__,
        )
        _reset_producer()
        return None