import logging
from typing import Optional

from confluent_kafka import KafkaError, KafkaException, Producer

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


# Error codes that mean "Kafka is unreachable or busy", not "this event is bad".
# Anything else Kafka reports (MSG_SIZE_TOO_LARGE, TOPIC_AUTHORIZATION_FAILED,
# INVALID_TOPIC_EXCEPTION, ...) is a problem with the event and counts towards
# OUTBOX_MAX_RETRIES.
BROKER_ERROR_CODES = {
    KafkaError._MSG_TIMED_OUT,
    KafkaError._TRANSPORT,
    KafkaError._ALL_BROKERS_DOWN,
    KafkaError._TIMED_OUT,
    KafkaError._QUEUE_FULL,
    KafkaError.REQUEST_TIMED_OUT,
    KafkaError.LEADER_NOT_AVAILABLE,
    KafkaError.NOT_LEADER_FOR_PARTITION,
    KafkaError.BROKER_NOT_AVAILABLE,
    KafkaError.NOT_ENOUGH_REPLICAS,
    KafkaError.NETWORK_EXCEPTION,
}


def classify_kafka_error(err: KafkaError) -> type[KafkaPublishError]:
    """Pick the exception class for a Kafka error, by its code (never its text)."""
    return KafkaBrokerError if err.code() in BROKER_ERROR_CODES else KafkaEventError


def is_broker_error(exc: Exception) -> bool:
    """
    True for a broker outage, False for a defect in the event itself.

    Anything we can't classify counts as an outage: it is retried forever but
    never dead-lettered, so an unexpected error can't silently lose an event.
    """
    return not isinstance(exc, KafkaEventError)


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
        except KafkaException as exc:
            err = exc.args[0]
            raise classify_kafka_error(err)(f"Message rejected by Kafka: {err}") from exc
        except BufferError as exc:
            # Local queue full: the broker isn't draining it.
            raise KafkaBrokerError(f"Could not enqueue message: {exc}") from exc

        remaining = self._producer.flush(timeout=5.0)

        if remaining > 0:
            raise KafkaBrokerError(
                f"Kafka did not acknowledge {remaining} message(s) within 5s"
            )

        if delivery_errors:
            err = delivery_errors[0]
            raise classify_kafka_error(err)(f"Delivery failed: {err}")

        return True
