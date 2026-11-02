import json
import logging
import os
from datetime import UTC, datetime
from kafka import KafkaProducer

log = logging.getLogger(__name__)

OUTPUT_TOPIC = "eta.shipment.predicted"


def create_producer() -> KafkaProducer:
    """Create the Kafka producer used by the ETA service."""
    return KafkaProducer(
        bootstrap_servers=os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            "localhost:9092",
        ),
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        key_serializer=lambda key: key.encode("utf-8"),
        acks="all",
        retries=3,
    )


def publish_prediction(
    producer: KafkaProducer,
    event: dict,
) -> None:
    """Publish an ETA prediction event using shipment_id as the Kafka key."""

    shipment_id = event["payload"]["shipment_id"]

    producer.send(
        OUTPUT_TOPIC,
        key=shipment_id,
        value=event,
    ).get()

    log.info(
        "Published ETA prediction: shipment_id=%s event_id=%s",
        shipment_id,
        event["event_id"],
    )

def publish_dlq(
    producer: KafkaProducer,
    raw_message: str,
    error_reason: str,
    topic: str,
    consumer_group: str,
    partition: int,
    offset: int,
) -> None:
    """Publish a failed ETA message to the dead-letter queue."""

    dlq_payload = {
        "raw_message": raw_message,
        "error": error_reason,
        "failed_at": datetime.now(UTC).isoformat(),
        "consumer_group": consumer_group,
        "topic": topic,
        "partition": partition,
        "offset": offset,
    }

    producer.send(
        "eta.shipment.dispatched.dlq",
        key=f"{topic}-{partition}-{offset}",
        value=dlq_payload,
    ).get()