from __future__ import annotations
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any
from confluent_kafka import (
    Consumer,
    KafkaError,
    KafkaException,
    Producer,
    TopicPartition,
)
from app.core.config import settings
from app.schemas.events import SupplierStatusChangedEvent
from app.services.supplier_compliance_service import (
    InvalidComplianceStatusError,
    SupplierComplianceError,
    supplier_compliance_service,
)

logger = logging.getLogger(__name__)

EVENT_TYPE = "compliance.supplier.status_changed"


class KafkaConsumerError(Exception):
    """Base exception for Supplier Portal Kafka consumer errors."""


class KafkaMessageValidationError(KafkaConsumerError):
    """Raised when a Kafka message violates the event contract."""


class KafkaDeadLetterError(KafkaConsumerError):
    """Raised when a Kafka message cannot be published to the DLQ."""


class SupplierStatusChangedConsumer:
    """Consume compliance events with retries and manual commits."""

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
        self._closed = False
        self._retries: dict[tuple[str, int, int], int] = {}

    @property
    def consumer(self) -> Consumer:
        """Return the underlying Kafka consumer."""
        return self._consumer

    def subscribe(self) -> None:
        """Subscribe to the configured Kafka topic."""
        self._consumer.subscribe([self.topic])
        logger.info(
            "Supplier Portal Kafka consumer subscribed: topic=%s group=%s",
            self.topic,
            self.group_id,
        )

    def close(self) -> None:
        """Attempt to close Kafka resources, even if one close fails."""
        if self._closed:
            return

        self._running = False
        self._closed = True
        errors: list[Exception] = []

        try:
            self._consumer.close()
        except Exception as exc:
            errors.append(exc)
            logger.exception("Failed to close the Kafka consumer.")

        try:
            remaining = self._dlq_producer.flush(timeout=5.0)
            if remaining:
                errors.append(
                    KafkaDeadLetterError(
                        f"{remaining} DLQ message(s) remained pending "
                        "at shutdown."
                    )
                )
                logger.error(
                    "DLQ producer still has %s message(s) pending "
                    "at shutdown.",
                    remaining,
                )
        except Exception as exc:
            errors.append(exc)
            logger.exception("Failed to flush the DLQ producer at shutdown.")

        if errors:
            raise KafkaConsumerError(
                "One or more Kafka resources failed to close cleanly."
            ) from errors[0]

        logger.info("Supplier Portal Kafka consumer closed.")

    def stop(self) -> None:
        """Request graceful shutdown."""
        self._running = False

    def process_message(self, message: Any) -> bool:
        """
        Deserialize, validate, and apply one compliance event.

        The supplier is identified by payload.supplier_name. The producer's
        Kafka key is also the name, but it is only used for partitioning.
        """
        event = self._deserialize_event(message)
        supplier_name = event.payload.supplier_name

        try:
            applied = supplier_compliance_service.apply_status_changed_event(event)
        except InvalidComplianceStatusError as exc:
            logger.exception(
                "Invalid compliance status: event_id=%s supplier_name=%s",
                event.event_id,
                supplier_name,
            )
            raise KafkaMessageValidationError(
                "Unsupported supplier compliance status."
            ) from exc
        except SupplierComplianceError:
            logger.exception(
                "Supplier compliance state update failed: event_id=%s supplier_name=%s",
                event.event_id,
                supplier_name,
            )
            raise

        if applied:
            logger.info(
                "Supplier compliance event applied: event_id=%s supplier_name=%s new_status=%s",
                event.event_id,
                supplier_name,
                event.payload.new_status,
            )
        else:
            logger.info(
                "Supplier compliance event ignored as duplicate or stale: "
                "event_id=%s supplier_name=%s occurred_at=%s",
                event.event_id,
                supplier_name,
                event.occurred_at,
            )

        return True

    def run(self, poll_timeout: float = 1.0) -> None:
        """Poll, process, retry failures, and commit only safe offsets."""
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

                retry_key = (
                    message.topic(),
                    message.partition(),
                    message.offset(),
                )

                try:
                    self.process_message(message)

                except KafkaMessageValidationError as exc:
                    logger.error(
                        "Rejected Kafka event; attempting DLQ delivery: %s",
                        exc,
                    )

                    committed = self._dead_letter_and_commit(
                        message=message,
                        reason=str(exc),
                    )

                    if committed:
                        self._retries.pop(retry_key, None)
                    elif not self._running:
                        raise KafkaConsumerError(
                            "Consumer stopped after a DLQ/commit failure."
                        )

                    continue

                except Exception as exc:
                    attempts = self._retries.get(retry_key, 0) + 1
                    self._retries[retry_key] = attempts
                    max_retries = max(1, settings.KAFKA_MAX_RETRIES)

                    if attempts >= max_retries:
                        logger.critical(
                            "COMPLIANCE EVENT NOT APPLIED; sent to DLQ "
                            "after %s attempts. Replay it from %s once "
                            "the cause is fixed: topic=%s partition=%s "
                            "offset=%s",
                            attempts,
                            self.dlq_topic,
                            message.topic(),
                            message.partition(),
                            message.offset(),
                        )

                        committed = self._dead_letter_and_commit(
                            message=message,
                            reason=(
                                f"failed after {attempts} attempts: {exc}"
                            ),
                        )

                        if committed:
                            self._retries.pop(retry_key, None)
                        elif not self._running:
                            raise KafkaConsumerError(
                                "Consumer stopped after a DLQ/commit failure."
                            )
                    else:
                        logger.exception(
                            "Processing failed (attempt %s/%s); "
                            "rewinding offset %s",
                            attempts,
                            max_retries,
                            message.offset(),
                        )

                        try:
                            self._rewind(message, attempts)
                        except Exception as rewind_exc:
                            logger.exception(
                                "Could not rewind failed message. "
                                "Consumer must be restarted."
                            )
                            self._running = False
                            raise KafkaConsumerError(
                                "Could not rewind the failed Kafka message."
                            ) from rewind_exc

                    continue

                # The service has returned only after its DB transaction.
                self._retries.pop(retry_key, None)

                if not self._safe_commit(message):
                    raise KafkaConsumerError(
                        "Offset commit failed; consumer restart required."
                    )

        except KeyboardInterrupt:
            logger.info("Supplier Portal Kafka consumer interrupted.")
        finally:
            self.close()

    def _rewind(self, message: Any, attempt: int = 1) -> None:
        """Seek back to the failed message and wait before retrying."""
        partition = TopicPartition(
            message.topic(),
            message.partition(),
            message.offset(),
        )

        self._consumer.seek(partition)

        delay = max(
            0.0,
            settings.KAFKA_RETRY_BACKOFF_SECONDS * attempt,
        )
        if delay:
            time.sleep(delay)

    def _dead_letter_and_commit(
        self,
        *,
        message: Any,
        reason: str,
    ) -> bool:
        """Commit the source offset only after confirmed DLQ delivery."""
        try:
            self._publish_to_dlq(
                message=message,
                error_reason=reason,
            )
        except Exception:
            logger.exception(
                "DLQ publish failed; original message will be retried."
            )

            try:
                self._rewind(message)
            except Exception as rewind_exc:
                logger.exception(
                    "Could not rewind message after DLQ failure. "
                    "Consumer must be restarted."
                )
                self._running = False
                raise KafkaConsumerError(
                    "Could not rewind the message after DLQ failure."
                ) from rewind_exc

            return False

        return self._safe_commit(message)

    def _safe_commit(self, message: Any) -> bool:
        """Commit synchronously and never silently skip a failed offset."""
        try:
            self._commit(message)
            return True
        except Exception:
            logger.exception(
                "Offset commit failed. Consumer restart required; "
                "the message may be redelivered."
            )
            self._running = False
            return False

    def _deserialize_event(
        self,
        message: Any,
    ) -> SupplierStatusChangedEvent:
        """Decode JSON and validate the event contract."""
        raw_value = message.value()

        if raw_value is None:
            raise KafkaMessageValidationError(
                "Kafka message has no value."
            )

        try:
            if isinstance(raw_value, bytes):
                raw_value = raw_value.decode("utf-8")
            elif not isinstance(raw_value, str):
                raise KafkaMessageValidationError(
                    "Kafka message value must be UTF-8 JSON."
                )

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

        if event.event_type != EVENT_TYPE:
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
        """Publish the original message and failure details to the DLQ."""
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

            logger.info(
                "Kafka event sent to DLQ: topic=%s partition=%s offset=%s",
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
        except Exception as exc:
            raise KafkaDeadLetterError(
                f"Unexpected error while publishing to DLQ: {exc}"
            ) from exc

        try:
            remaining = self._dlq_producer.flush(timeout=5.0)
        except Exception as exc:
            raise KafkaDeadLetterError(
                f"Failed to flush DLQ message: {exc}"
            ) from exc

        if remaining > 0:
            raise KafkaDeadLetterError(
                f"Kafka did not acknowledge {remaining} DLQ message(s) "
                "within 5 seconds."
            )

        if delivery_errors:
            raise KafkaDeadLetterError(
                f"DLQ delivery failed: {delivery_errors[0]}"
            )

    def _commit(self, message: Any) -> None:
        """Synchronously commit a message offset."""
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
            "Kafka offset committed: topic=%s partition=%s offset=%s",
            message.topic(),
            message.partition(),
            message.offset(),
        )

    @staticmethod
    def _handle_consumer_error(error: KafkaError) -> None:
        """Handle Kafka client and broker errors."""
        if error.code() == KafkaError._PARTITION_EOF:
            logger.debug("Reached Kafka partition EOF.")
            return

        logger.error("Kafka consumer error: %s", error)
