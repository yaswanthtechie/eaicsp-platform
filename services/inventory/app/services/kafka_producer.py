import logging
from typing import Any, Optional

try:
    from confluent_kafka import Producer as ConfluentProducer
    CONFLUENT_KAFKA_AVAILABLE = True
except ImportError:
    CONFLUENT_KAFKA_AVAILABLE = False

from app.core.config import settings

logger = logging.getLogger(__name__)


class KafkaPublishError(Exception):
    """Raised when an event fails to publish to Kafka."""
    pass


class KafkaEventPublisher:
    """
    Kafka Event Publisher wrapper supporting confluent-kafka with delivery verification.
    Also provides simulated/mock modes for testing and graceful failure handling.
    """

    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        mock_mode: bool = False,
    ):
        self.bootstrap_servers = bootstrap_servers or getattr(
            settings, "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self.mock_mode = mock_mode
        self.published_messages: list[dict[str, Any]] = []
        self._producer = None

        if not self.mock_mode and CONFLUENT_KAFKA_AVAILABLE:
            try:
                self._producer = ConfluentProducer(
                    {
                        "bootstrap.servers": self.bootstrap_servers,
                        "client.id": "inventory-outbox-relay",
                        "acks": "all",
                        "retries": 3,
                        "socket.timeout.ms": 3000,
                        "message.timeout.ms": 5000,
                    }
                )
            except Exception as exc:
                logger.warning(
                    "Could not initialize Confluent Kafka producer: %s. Falling back to mock.",
                    exc,
                )
                self._producer = None

    def publish(
        self,
        topic: str,
        key: str,
        value: str,
    ) -> bool:
        """
        Publish message to Kafka topic.
        Returns True if acknowledged by Kafka, raises KafkaPublishError on failure.
        """
        if self.mock_mode or self._producer is None:
            # Record in-memory for testing
            self.published_messages.append(
                {
                    "topic": topic,
                    "key": key,
                    "value": value,
                }
            )
            logger.info("Published event to [mock] Kafka topic %s with key %s", topic, key)
            return True

        delivery_error: list[Optional[Exception]] = [None]

        def _delivery_callback(err, msg):
            if err is not None:
                delivery_error[0] = KafkaPublishError(f"Delivery failed: {err}")
            else:
                logger.info(
                    "Message delivered to %s [%s] @ offset %s",
                    msg.topic(),
                    msg.partition(),
                    msg.offset(),
                )

        try:
            self._producer.produce(
                topic=topic,
                key=key.encode("utf-8") if key else None,
                value=value.encode("utf-8"),
                callback=_delivery_callback,
            )
            # Flush with timeout to ensure message is sent and callback executes
            remaining = self._producer.flush(timeout=5.0)
            if remaining > 0:
                raise KafkaPublishError(f"Kafka flush timed out; {remaining} messages unsent")

            if delivery_error[0] is not None:
                raise delivery_error[0]

            return True

        except Exception as exc:
            logger.error("Failed to publish to Kafka topic %s: %s", topic, exc)
            raise KafkaPublishError(str(exc)) from exc
