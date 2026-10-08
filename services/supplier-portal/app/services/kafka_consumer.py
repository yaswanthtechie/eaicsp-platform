from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer

from app.core.config import settings
from app.schemas.events import SupplierStatusChangedEvent
from app.services.supplier_compliance_service import (
    InvalidComplianceStatusError,
    SupplierComplianceError,
    SupplierNotFoundError,
    supplier_compliance_service,
)

logger = logging.getLogger(__name__)


class KafkaConsumerError(Exception):
    """Base exception for Supplier Portal Kafka consumer errors."""


class KafkaMessageValidationError(KafkaConsumerError):
    """Raised when a Kafka message is malformed or violates the event contract."""


class KafkaDeadLetterError(KafkaConsumerError):
    """Raised when a bad Kafka message cannot be published to the DLQ."""


class SupplierStatusChangedConsumer:
    """
    Kafka consumer for compliance.supplier.status_changed events.

    Responsibilities:
    - Consume supplier compliance status-change events.
    - Validate the event envelope and payload.
    - Apply supplier compliance access state.
    - Preserve idempotency and out-of-order handling through
      SupplierComplianceService.
    - Commit offsets only after successful processing.
    - Send invalid/poison messages to the dead-letter topic.
    - Never commit the original message when DLQ publishing fails.
    """

    EVENT_VERSION = 1

    def __init__(
        self,
        *,
        bootstrap_servers: str | None = None,
        topic: str | None = None,
        group_id: str | None = None,
        dlq_topic: str | None = None,
        auto_offset_reset: str | None = None,
    ) -> None:
        self.bootstrap_servers = (
            bootstrap_servers or settings.KAFKA_BOOTSTRAP_SERVERS
        )
        self.topic = topic or settings.KAFKA_STATUS_CHANGED_TOPIC
        self.group_id = group_id or settings.KAFKA_CONSUMER_GROUP
        self.dlq_topic = dlq_topic or settings.KAFKA_DLQ_TOPIC
        self.auto_offset_reset = (
            auto_offset_reset or settings.KAFKA_AUTO_OFFSET_RESET
        )

        self._consumer = Consumer(
            {
                "bootstrap.servers": self.bootstrap_servers,
                "group.id": self.group_id,
                "auto.offset.reset": self.auto_offset_reset,
                "enable.auto.commit": False,
            }
        )

        self._dlq_producer = Producer(
            {
                "bootstrap.servers": self.bootstrap_servers,
                "client.id": "supplier-portal-dlq-producer",
                "acks": "all",
                "enable.idempotence": True,
                "retries": 3,
                "message.timeout.ms": 5000,
            }
        )

        self._running = False

    @property
    def consumer(self) -> Consumer:
        """Return the underlying Kafka consumer."""
        return self._consumer

    def subscribe(self) -> None:
        """Subscribe to the configured supplier compliance topic."""
        self._consumer.subscribe([self.topic])

        logger.info(
            "Supplier Portal Kafka consumer subscribed: "
            "topic=%s group=%s",
            self.topic,
            self.group_id,
        )

    def close(self) -> None:
        """
        Close Kafka resources gracefully.

        Calling close multiple times is safe.
        """
        self._running = False

        try:
            self._consumer.close()
        finally:
            self._dlq_producer.flush(timeout=5.0)

        logger.info("Supplier Portal Kafka consumer closed.")

    def stop(self) -> None:
        """Request graceful shutdown of the consumer loop."""
        self._running = False

    def process_message(self, message: Any) -> bool:
        """
        Deserialize, validate, and apply one Kafka event.

        Returns:
            True when the event was successfully processed.

        Raises:
            KafkaMessageValidationError:
                The message violates the event contract.

            SupplierNotFoundError:
                The event references an unknown supplier.

            SupplierComplianceError:
                Supplier compliance state could not be updated.
        """
        event = self._deserialize_event(message)

        try:
            applied = supplier_compliance_service.apply_status_changed_event(
                event
            )

        except SupplierNotFoundError:
            logger.exception(
                "Supplier referenced by compliance event does not exist: "
                "event_id=%s supplier_id=%s",
                event.event_id,
                event.payload.supplier_id,
            )
            raise

        except InvalidComplianceStatusError as exc:
            logger.exception(
                "Invalid compliance status in event: event_id=%s",
                event.event_id,
            )
            raise KafkaMessageValidationError(
                "Unsupported supplier compliance status."
            ) from exc

        except SupplierComplianceError:
            logger.exception(
                "Supplier compliance state update failed: event_id=%s",
                event.event_id,
            )
            raise

        if applied:
            logger.info(
                "Supplier compliance event applied successfully: "
                "event_id=%s supplier_id=%s new_status=%s",
                event.event_id,
                event.payload.supplier_id,
                event.payload.new_status,
            )
        else:
            logger.info(
                "Supplier compliance event ignored because it is "
                "duplicate or out-of-order: "
                "event_id=%s supplier_id=%s occurred_at=%s",
                event.event_id,
                event.payload.supplier_id,
                event.occurred_at,
            )

        return True

    def run(self, poll_timeout: float = 1.0) -> None:
        """
        Start the Kafka consumer loop.

        Offset commit order:

            poll
              ↓
            validate
              ↓
            apply state
              ↓
            commit offset

        Therefore a processing failure never causes the original offset
        to be committed.
        """
        self.subscribe()
        self._running = True

        logger.info(
            "Supplier Portal Kafka consumer started: "
            "topic=%s group=%s bootstrap=%s",
            self.topic,
            self.group_id,
            self.bootstrap_servers,
        )

        try:
            while self._running:
                message = self._consumer.poll(timeout=poll_timeout)

                if message is None:
                    continue

                if message.error():
                    self._handle_consumer_error(message.error())
                    continue

                try:
                    self.process_message(message)

                except KafkaMessageValidationError as exc:
                    logger.error(
                        "Invalid Kafka event. Sending message to DLQ: %s",
                        exc,
                    )

                    self._publish_to_dlq(
                        message=message,
                        error_reason=str(exc),
                    )

                    self._commit(message)
                    continue

                except SupplierNotFoundError as exc:
                    logger.error(
                        "Kafka event references an unknown supplier. "
                        "Sending message to DLQ: %s",
                        exc,
                    )

                    self._publish_to_dlq(
                        message=message,
                        error_reason=str(exc),
                    )

                    self._commit(message)
                    continue

                except SupplierComplianceError:
                    logger.exception(
                        "Supplier compliance processing failed. "
                        "Original Kafka offset will NOT be committed."
                    )
                    continue

                except Exception:
                    logger.exception(
                        "Unexpected Kafka message processing failure. "
                        "Original Kafka offset will NOT be committed."
                    )
                    continue

                self._commit(message)

        except KeyboardInterrupt:
            logger.info("Supplier Portal Kafka consumer interrupted.")

        finally:
            self.close()

    def _deserialize_event(
        self,
        message: Any,
    ) -> SupplierStatusChangedEvent:
        """
        Decode and validate one Kafka message.

        Validation includes:
        - valid UTF-8
        - valid JSON
        - JSON object
        - Pydantic event schema
        - expected event type
        - supported event version
        """
        raw_value = message.value()

        if raw_value is None:
            raise KafkaMessageValidationError(
                "Kafka message has no value."
            )

        try:
            if isinstance(raw_value, bytes):
                raw_value = raw_value.decode("utf-8")

            data = json.loads(raw_value)

        except UnicodeDecodeError as exc:
            raise KafkaMessageValidationError(
                "Kafka message contains invalid UTF-8 data."
            ) from exc

        except json.JSONDecodeError as exc:
            raise KafkaMessageValidationError(
                "Kafka message is not valid JSON."
            ) from exc

        if not isinstance(data, dict):
            raise KafkaMessageValidationError(
                "Kafka event must be a JSON object."
            )

        try:
            event = SupplierStatusChangedEvent.model_validate(data)

        except Exception as exc:
            raise KafkaMessageValidationError(
                "Kafka event does not match the Supplier Portal "
                "event contract."
            ) from exc

        if event.event_type != self.topic:
            raise KafkaMessageValidationError(
                f"Unexpected event type: {event.event_type}"
            )

        if event.event_version != self.EVENT_VERSION:
            raise KafkaMessageValidationError(
                f"Unsupported event version: {event.event_version}"
            )

        return event

    def _publish_to_dlq(
        self,
        *,
        message: Any,
        error_reason: str,
    ) -> None:
        """
        Publish a failed Kafka message to the dead-letter topic.

        The original Kafka offset is intentionally NOT committed here.

        The caller commits the original offset only after this method
        completes successfully.
        """
        delivery_errors: list[Any] = []

        original_value = message.value()

        if isinstance(original_value, bytes):
            original_value = original_value.decode(
                "utf-8",
                errors="replace",
            )

        original_key = message.key()

        if isinstance(original_key, bytes):
            original_key = original_key.decode(
                "utf-8",
                errors="replace",
            )

        dlq_payload = {
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "error_reason": error_reason,
            "source_topic": message.topic(),
            "source_partition": message.partition(),
            "source_offset": message.offset(),
            "original_key": original_key,
            "original_value": original_value,
        }

        def _on_delivery(
            error: KafkaError | None,
            delivered_message: Any,
        ) -> None:
            if error is not None:
                delivery_errors.append(error)
                return

            logger.warning(
                "Kafka event sent to DLQ successfully: "
                "topic=%s partition=%s offset=%s",
                delivered_message.topic(),
                delivered_message.partition(),
                delivered_message.offset(),
            )

        try:
            self._dlq_producer.produce(
                topic=self.dlq_topic,
                key=message.key(),
                value=json.dumps(dlq_payload),
                on_delivery=_on_delivery,
            )

        except BufferError as exc:
            raise KafkaDeadLetterError(
                f"DLQ producer queue is full: {exc}"
            ) from exc

        except KafkaException as exc:
            raise KafkaDeadLetterError(
                f"Could not publish event to DLQ: {exc}"
            ) from exc

        remaining = self._dlq_producer.flush(timeout=5.0)

        if remaining > 0:
            raise KafkaDeadLetterError(
                "Kafka did not acknowledge "
                f"{remaining} DLQ message(s) within 5 seconds."
            )

        if delivery_errors:
            raise KafkaDeadLetterError(
                f"DLQ delivery failed: {delivery_errors[0]}"
            )

    def _commit(self, message: Any) -> None:
        """
        Commit one Kafka offset synchronously.

        Synchronous commit is intentional here because we must know that
        Kafka accepted the offset before continuing.
        """
        try:
            self._consumer.commit(
                message=message,
                asynchronous=False,
            )

        except KafkaException:
            logger.exception(
                "Kafka offset commit failed: "
                "topic=%s partition=%s offset=%s",
                message.topic(),
                message.partition(),
                message.offset(),
            )
            raise

        logger.debug(
            "Kafka offset committed: "
            "topic=%s partition=%s offset=%s",
            message.topic(),
            message.partition(),
            message.offset(),
        )

    @staticmethod
    def _handle_consumer_error(error: KafkaError) -> None:
        """Handle Kafka client/broker errors."""
        if error.code() == KafkaError._PARTITION_EOF:
            logger.debug("Reached Kafka partition EOF.")
            return

        logger.error(
            "Kafka consumer error: %s",
            error,
        )