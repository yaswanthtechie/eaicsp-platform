import logging
from typing import Optional

from confluent_kafka import Producer

from app.core.config import settings

logger = logging.getLogger(__name__)


class KafkaPublishError(Exception):
    """Raised when Kafka does not acknowledge an event."""


class KafkaEventPublisher:
    """
    Real Kafka publisher used by the outbox relay.

    There is deliberately NO in-memory fallback here:
    - if confluent-kafka is missing, the import above fails at startup;
    - if the broker does not acknowledge a message, publish() raises,
      so the relay leaves the event in the outbox and retries later.

    The test fake lives in tests/fakes.py.
    """

    def __init__(self, bootstrap_servers: Optional[str] = None):
        self.bootstrap_servers = (
            bootstrap_servers or settings.KAFKA_BOOTSTRAP_SERVERS
        )
        self._producer = Producer(
            {
                "bootstrap.servers": self.bootstrap_servers,
                "client.id": "inventory-outbox-relay",
                "acks": "all",
                "retries": 3,
                "socket.timeout.ms": 3000,
                "message.timeout.ms": 5000,
            }
        )

    def publish(self, topic: str, key: str, value: str) -> bool:
        """Publish one message and wait for Kafka's acknowledgement."""
        delivery_errors = []

        def _on_delivery(err, msg):
            if err is not None:
                delivery_errors.append(err)
            else:
                logger.info(
                    "Delivered to %s [%s] @ offset %s",
                    msg.topic(),
                    msg.partition(),
                    msg.offset(),
                )

        try:
            self._producer.produce(
                topic=topic,
                key=key.encode("utf-8") if key else None,
                value=value.encode("utf-8"),
                on_delivery=_on_delivery,
            )
        except Exception as exc:
            raise KafkaPublishError(f"Could not enqueue message: {exc}") from exc

        remaining = self._producer.flush(timeout=5.0)

        if remaining > 0:
            raise KafkaPublishError(
                f"Kafka did not acknowledge {remaining} message(s) within 5s"
            )

        if delivery_errors:
            raise KafkaPublishError(f"Delivery failed: {delivery_errors[0]}")

        return True
