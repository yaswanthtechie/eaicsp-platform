import logging
from typing import Optional

from confluent_kafka import Producer

from app.core.config import settings

logger = logging.getLogger(__name__)


class KafkaPublishError(Exception):
    """Base exception for Kafka publish errors."""


class KafkaBrokerError(KafkaPublishError):
    """
    Raised when the Kafka broker is unreachable, down, or fails to acknowledge.
    Represents an infrastructure/network outage, NOT a defective event.
    """


class KafkaEventError(KafkaPublishError):
    """
    Raised when Kafka rejects an event due to payload defects (e.g. message too large).
    Represents a poison pill caused by the event itself.
    """


def is_broker_error(exc: Exception) -> bool:
    """
    Classify whether an exception represents a broker outage or an event-level defect.
    """
    if isinstance(exc, KafkaBrokerError):
        return True
    if isinstance(exc, KafkaEventError):
        return False
    msg = str(exc).lower()
    # Explicit poison pill / event defects:
    if "too large" in msg or "msgsize" in msg or "poison" in msg or "malformed" in msg:
        return False
    # Everything else (connection refused, timeout, unreachable broker, not acknowledge):
    return True


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
            err_str = str(exc).lower()
            if "too large" in err_str or "msgsize" in err_str:
                raise KafkaEventError(f"Message rejected by Kafka: {exc}") from exc
            raise KafkaBrokerError(f"Could not enqueue message: {exc}") from exc

        remaining = self._producer.flush(timeout=5.0)

        if remaining > 0:
            raise KafkaBrokerError(
                f"Kafka did not acknowledge {remaining} message(s) within 5s"
            )

        if delivery_errors:
            err = delivery_errors[0]
            err_str = str(err).lower()
            if "too large" in err_str or "msgsize" in err_str:
                raise KafkaEventError(f"Delivery failed: {err}")
            raise KafkaBrokerError(f"Delivery failed: {err}")

        return True
