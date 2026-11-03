import json
import logging
import os
from datetime import datetime, timezone

from confluent_kafka import Producer

log = logging.getLogger(__name__)


class PublishError(RuntimeError):
    """A message could not be delivered to Kafka."""


def create_producer() -> Producer:
    """Create the Kafka producer used by the ETA service."""
    return Producer(
        {
            "bootstrap.servers": os.getenv(
                "KAFKA_BOOTSTRAP_SERVERS",
                "localhost:9092",
            ),
            "acks": "all",
            "enable.idempotence": True,
        }
    )


def _send(
    producer: Producer,
    topic: str,
    key: str,
    value: dict,
    timeout: float = 10.0,
) -> None:
    errors = []

    def on_delivery(err, _msg):
        if err is not None:
            errors.append(err)

    producer.produce(
        topic,
        key=key.encode("utf-8"),
        value=json.dumps(value).encode("utf-8"),
        on_delivery=on_delivery,
    )

    remaining = producer.flush(timeout)

    if errors or remaining:
        raise PublishError(
            f"Publish to {topic} failed: "
            f"{errors or 'flush timed out'}"
        )


def publish_prediction(
    producer: Producer,
    event: dict,
    topic: str,
) -> None:
    """Publish an ETA prediction event using shipment_id as the Kafka key."""
    shipment_id = event["payload"]["shipment_id"]

    _send(producer, topic, shipment_id, event)

    log.info(
        "Published ETA prediction: shipment_id=%s event_id=%s",
        shipment_id,
        event["event_id"],
    )


def publish_dlq(
    producer: Producer,
    *,
    dlq_topic: str,
    raw_message: str,
    error_reason: str,
    topic: str,
    consumer_group: str,
    partition: int,
    offset: int,
) -> None:
    """Publish a failed message to the dead-letter queue."""
    _send(
        producer,
        dlq_topic,
        f"{topic}-{partition}-{offset}",
        {
            "raw_message": raw_message,
            "error": error_reason,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "consumer_group": consumer_group,
            "topic": topic,
            "partition": partition,
            "offset": offset,
        },
    )
