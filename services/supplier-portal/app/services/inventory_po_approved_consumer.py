from __future__ import annotations

import json
import logging
import time
from typing import Any

from confluent_kafka import Consumer, KafkaException, Producer
from pydantic import ValidationError

from app.core.config import settings
from app.database import SessionLocal
from app.models.po_mirror import POMirror
from app.schemas.events import POApprovedEvent

logger = logging.getLogger(__name__)


class POApprovedConsumer:
    """Consume approved PO events and persist them before offset commit."""

    def __init__(self) -> None:
        self.consumer: Consumer | None = None
        self.producer: Producer | None = None
        self._running = False

    def _commit(self, message: Any) -> None:
        """Commit the source offset after successful processing."""
        if self.consumer is None:
            raise RuntimeError("Kafka consumer is not initialized")

        self.consumer.commit(message=message, asynchronous=False)

    @staticmethod
    def _decode_original_event(raw_value: bytes | None) -> Any:
        """Decode the original message for diagnostic DLQ storage."""
        if not raw_value:
            return None

        try:
            return json.loads(raw_value.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return raw_value.decode("utf-8", errors="replace")

    def _publish_dlq(self, message: Any, reason: str) -> None:
        """Publish to the DLQ and commit the source offset only on success."""
        if self.producer is None:
            raise RuntimeError("Kafka producer is not initialized")

        raw_value = message.value()
        raw_key = message.key()
        delivery_errors: list[str] = []

        original_event = self._decode_original_event(raw_value)

        def on_delivery(error: Any, delivered_message: Any) -> None:
            if error is not None:
                delivery_errors.append(str(error))

        dlq_record = {
            "source_topic": message.topic(),
            "source_partition": message.partition(),
            "source_offset": message.offset(),
            "error": reason[:1000],
            "original_event": original_event,
        }

        self.producer.produce(
            topic=settings.PO_DLQ_TOPIC,
            key=raw_key,
            value=json.dumps(dlq_record),
            on_delivery=on_delivery,
        )

        pending = self.producer.flush(10)

        # confluent_kafka.Producer.flush() returns the number of messages
        # still queued. Treat an unexpected return type as a failure rather
        # than allowing a TypeError or assuming delivery succeeded.
        if not isinstance(pending, int):
            raise RuntimeError(
                "DLQ delivery could not be confirmed: "
                f"unexpected flush result {type(pending).__name__}"
            )

        if pending > 0 or delivery_errors:
            raise RuntimeError(
                "DLQ delivery failed; "
                f"pending={pending}, errors={delivery_errors}"
            )

        # The source message is acknowledged only after DLQ delivery.
        self._commit(message)

        logger.error(
            "PO event sent to DLQ: topic=%s partition=%s offset=%s reason=%s",
            message.topic(),
            message.partition(),
            message.offset(),
            reason,
        )

    def _persist_event(self, event: POApprovedEvent) -> None:
        """Persist one approved PO idempotently in a database transaction."""
        payload = event.payload
        event_lines = [
            line.model_dump(mode="json")
            for line in payload.lines
        ]

        with SessionLocal() as db:
            try:
                # Exact replay: the same event has already been persisted.
                existing_event = (
                    db.query(POMirror)
                    .filter(POMirror.event_id == event.event_id)
                    .one_or_none()
                )

                if existing_event is not None:
                    db.rollback()
                    logger.info(
                        "Duplicate PO event ignored: event_id=%s po_id=%s",
                        event.event_id,
                        payload.po_id,
                    )
                    return

                # A PO ID is unique. Never overwrite an existing PO with a
                # different event, even when the payload looks identical.
                existing_po = (
                    db.query(POMirror)
                    .filter(POMirror.po_id == payload.po_id)
                    .one_or_none()
                )

                if existing_po is not None:
                    same_payload = (
                        existing_po.po_number == payload.po_number
                        and existing_po.supplier_id == payload.supplier_id
                        and existing_po.warehouse_id == payload.warehouse_id
                        and existing_po.approval_status
                        == payload.approval_status
                        and existing_po.approved_by == payload.approved_by
                        and existing_po.approved_at == payload.approved_at
                        and existing_po.total_amount == payload.total_amount
                        and existing_po.currency == payload.currency
                        and existing_po.expected_delivery_date
                        == payload.expected_delivery_date
                        and existing_po.lines == event_lines
                    )

                    db.rollback()

                    if same_payload:
                        logger.warning(
                            "Duplicate approved PO ignored: po_id=%s "
                            "existing_event_id=%s incoming_event_id=%s",
                            payload.po_id,
                            existing_po.event_id,
                            event.event_id,
                        )
                        return

                    raise ValueError(
                        "Conflicting approved PO event for "
                        f"existing po_id={payload.po_id}"
                    )

                po = POMirror(
                    po_id=payload.po_id,
                    event_id=event.event_id,
                    po_number=payload.po_number,
                    supplier_id=payload.supplier_id,
                    warehouse_id=payload.warehouse_id,
                    approval_status=payload.approval_status,
                    approved_by=payload.approved_by,
                    approved_at=payload.approved_at,
                    total_amount=payload.total_amount,
                    currency=payload.currency,
                    expected_delivery_date=payload.expected_delivery_date,
                    lines=event_lines,
                    event_type=event.event_type,
                    event_version=event.event_version,
                    occurred_at=event.occurred_at,
                    trace_id=event.trace_id,
                    status="approved",
                )

                db.add(po)
                db.commit()

                logger.info(
                    "Approved PO persisted: event_id=%s po_id=%s",
                    event.event_id,
                    payload.po_id,
                )

            except Exception:
                db.rollback()
                raise

    def _process_message(self, message: Any) -> None:
        """Validate, persist and acknowledge a single Kafka message."""
        # Kafka transport errors are not malformed business events.
        # Log them and leave the source offset uncommitted.
        message_error = message.error()
        if message_error:
            logger.error("PO Kafka message error: %s", message_error)
            return

        raw_value = message.value()

        try:
            if not raw_value:
                raise ValueError("Empty Kafka message")

            raw_event = json.loads(raw_value.decode("utf-8"))
            event = POApprovedEvent.model_validate(raw_event)

        except (
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValidationError,
        ) as exc:
            self._publish_dlq(message, f"Invalid PO event: {exc}")
            return

        max_retries = max(1, int(settings.PO_MAX_RETRIES))
        backoff = max(0.0, float(settings.PO_RETRY_BACKOFF_SECONDS))

        for attempt in range(1, max_retries + 1):
            try:
                # The database transaction completes inside _persist_event.
                # Duplicate replays also return successfully.
                self._persist_event(event)

            except Exception as exc:
                logger.exception(
                    "PO persistence failed: event_id=%s attempt=%s/%s",
                    event.event_id,
                    attempt,
                    max_retries,
                )

                if attempt < max_retries:
                    time.sleep(backoff)
                    continue

                # If DLQ delivery fails, this exception propagates and the
                # source offset remains uncommitted.
                self._publish_dlq(
                    message,
                    "Persistence failed after "
                    f"{max_retries} attempts: {exc}",
                )
                return

            # Commit only after DB persistence or idempotent duplicate
            # detection succeeds. Do not include this in the DB retry block.
            self._commit(message)

            logger.info(
                "Approved PO event processed: event_id=%s po_id=%s",
                event.event_id,
                event.payload.po_id,
            )
            return

    def run(self) -> None:
        """Start the Kafka consumer loop."""
        if self._running:
            logger.warning("PO consumer is already running")
            return

        self.consumer = Consumer(
            {
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "group.id": settings.PO_CONSUMER_GROUP,
                "auto.offset.reset": settings.PO_AUTO_OFFSET_RESET,
                "enable.auto.commit": False,
                "enable.auto.offset.store": False,
            }
        )

        self.producer = Producer(
            {
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            }
        )

        self.consumer.subscribe([settings.PO_APPROVED_TOPIC])
        self._running = True

        logger.info(
            "PO consumer started: topic=%s group=%s",
            settings.PO_APPROVED_TOPIC,
            settings.PO_CONSUMER_GROUP,
        )

        try:
            while self._running:
                message = self.consumer.poll(1.0)

                if message is None:
                    continue

                if message.error():
                    # Consumer-level errors should not be treated as
                    # invalid PO events or sent to the DLQ.
                    logger.error(
                        "PO Kafka consumer error: %s",
                        message.error(),
                    )
                    continue

                # Persistence, DLQ and offset-commit failures propagate.
                # An uncommitted message can be replayed safely.
                self._process_message(message)

        except KafkaException:
            logger.exception("PO Kafka consumer stopped due to Kafka error")
            raise

        finally:
            self._running = False

            if self.consumer is not None:
                try:
                    self.consumer.close()
                except Exception:
                    logger.exception("Failed to close PO Kafka consumer")
                finally:
                    self.consumer = None

            if self.producer is not None:
                try:
                    remaining = self.producer.flush(5)

                    if isinstance(remaining, int) and remaining > 0:
                        logger.warning(
                            "PO Kafka producer shutdown with %s "
                            "pending messages",
                            remaining,
                        )
                except Exception:
                    logger.exception("Failed to flush PO Kafka producer")
                finally:
                    self.producer = None

    def stop(self) -> None:
        """Request graceful shutdown of the polling loop."""
        self._running = False
