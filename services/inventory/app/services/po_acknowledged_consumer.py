from datetime import UTC, datetime, timedelta
from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.core.config import settings
from app.models.compliance_event import ProcessedEvent
from app.models.purchase_order import PurchaseOrder
from app.schemas.events import POAcknowledgedPayload

try:
    from confluent_kafka import Consumer, KafkaError, KafkaException, TopicPartition
except ImportError:
    Consumer = None
    KafkaError = None
    KafkaException = None
    TopicPartition = None

logger = logging.getLogger(__name__)

EVENT_TYPE = "supplierportal.po.acknowledged"
SUPPORTED_EVENT_VERSIONS = {1}
MAX_FUTURE_SKEW = timedelta(minutes=5)


class InvalidMessageError(Exception):
    """Raised when an incoming Kafka message is malformed, unparseable, or violates schema."""


class DeadLetterPublishError(Exception):
    """Raised when a bad message could not be written to the DLQ (so its offset must not be committed)."""


@dataclass
class ProcessingResult:
    status: str  # "PROCESSED", "DUPLICATE", "PO_NOT_FOUND", "SKIPPED_INVALID_STATE", "DLQ"
    event_id: str
    affected_po: Optional[str] = None
    details: str = ""


def parse_iso_datetime(dt_str: Any) -> datetime:
    """Parse ISO8601 string to timezone-aware UTC datetime."""
    if not isinstance(dt_str, str):
        raise ValueError(f"Expected ISO datetime string, got {type(dt_str)}")

    normalized = dt_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt


def _record_processed(
    db: Session,
    *,
    event_id: str,
    event_type: str,
    supplier_id: Optional[str],
    occurred_at: Optional[datetime],
    status: str,
) -> None:
    db.add(
        ProcessedEvent(
            event_id=event_id,
            event_type=event_type,
            supplier_id=supplier_id,
            occurred_at=occurred_at,
            status=status,
            processed_at=datetime.now(UTC),
        )
    )


def _commit_or_duplicate(db: Session, event_id: str) -> bool:
    """
    Commit the transaction. Returns False if a concurrent delivery of the same
    event_id committed first (primary-key race), indicating duplicate.
    """
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        if (
            db.query(ProcessedEvent)
            .filter(ProcessedEvent.event_id == event_id)
            .first()
            is not None
        ):
            return False
        raise
    except Exception:
        db.rollback()
        raise


def process_po_acknowledged_event(
    db: Session,
    event_data: dict[str, Any],
) -> ProcessingResult:
    """
    Process supplierportal.po.acknowledged event (Flow B).

    Guarantees:
    - Idempotency: Duplicate event_ids leave state untouched.
    - Locks the PO row with `with_for_update()`.
    - If PO exists and is not already received/partially received, updates status to 'acknowledged'.
    - Commits the idempotency record and the PO status atomically.
    """
    # 1. Envelope validation
    event_id = event_data.get("event_id")
    event_type = event_data.get("event_type")
    event_version = event_data.get("event_version")
    payload = event_data.get("payload")

    if not isinstance(event_id, str) or not event_id:
        raise InvalidMessageError("Missing or invalid 'event_id' in event envelope")
    if event_type != EVENT_TYPE:
        raise InvalidMessageError(
            f"Unexpected event_type {event_type!r} (expected {EVENT_TYPE!r})"
        )
    if isinstance(event_version, bool) or event_version not in SUPPORTED_EVENT_VERSIONS:
        raise InvalidMessageError(
            f"Unknown or unsupported event_version: {event_version!r} "
            f"(supported: {sorted(SUPPORTED_EVENT_VERSIONS)})"
        )
    if not isinstance(payload, dict) or not payload:
        raise InvalidMessageError("Missing or invalid 'payload' object in event envelope")

    # 2. Payload validation against the contract
    try:
        ack = POAcknowledgedPayload.model_validate(payload)
    except ValidationError as exc:
        raise InvalidMessageError(
            f"Payload does not match supplierportal.po.acknowledged v1: {exc}"
        ) from exc
    po_number = ack.po_number
    supplier_id = ack.supplier_id

    occurred_at_raw = event_data.get("occurred_at")
    try:
        occurred_at = parse_iso_datetime(occurred_at_raw) if occurred_at_raw else None
    except Exception as exc:
        raise InvalidMessageError(f"Invalid 'occurred_at' timestamp: {occurred_at_raw}") from exc

    if occurred_at and occurred_at > datetime.now(UTC) + MAX_FUTURE_SKEW:
        raise InvalidMessageError(
            f"'occurred_at' {occurred_at.isoformat()} is in the future; rejected"
        )

    # 3. Idempotency check
    existing = (
        db.query(ProcessedEvent)
        .filter(ProcessedEvent.event_id == event_id)
        .first()
    )
    if existing is not None:
        logger.info(
            "Event %s already processed at %s (%s). Skipping.",
            event_id,
            existing.processed_at,
            existing.status,
        )
        return ProcessingResult(
            status="DUPLICATE",
            event_id=event_id,
            details=f"Event {event_id} already processed",
        )

    # 4. Find and lock the purchase order
    po = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.po_id == po_number)
        .with_for_update()
        .first()
    )

    if po is None:
        logger.warning(
            "PO %s not found for acknowledgement event %s. Recording skipped.",
            po_number,
            event_id,
        )
        _record_processed(
            db,
            event_id=event_id,
            event_type=event_type,
            supplier_id=supplier_id,
            occurred_at=occurred_at,
            status="SKIPPED_PO_NOT_FOUND",
        )
        if not _commit_or_duplicate(db, event_id):
            return ProcessingResult(
                status="DUPLICATE",
                event_id=event_id,
                details=f"Event {event_id} already processed concurrently",
            )
        return ProcessingResult(
            status="PO_NOT_FOUND",
            event_id=event_id,
            details=f"Purchase order {po_number} not found",
        )

    # 5. The sender must own the PO. A mismatch is a bad message, so it goes to the DLQ.
    if po.supplier_id != supplier_id:
        raise InvalidMessageError(
            f"Supplier {supplier_id} does not own PO {po.po_id} (owner is {po.supplier_id})"
        )

    # 6. Only an approved draft moves to 'acknowledged'. Later states stay as they are.
    if po.status == "draft" and po.approval_status == "approved":
        po.status = "acknowledged"
        outcome = "PROCESSED"
        details = f"PO {po.po_id} marked as acknowledged"
    elif po.status in ("acknowledged", "received", "partially_received"):
        outcome = "PROCESSED"
        details = f"PO {po.po_id} already {po.status}; nothing to change"
    else:
        outcome = "SKIPPED_INVALID_STATE"
        details = (
            f"PO {po.po_id} is {po.status}/{po.approval_status}; "
            "only approved draft POs can be acknowledged"
        )
        logger.warning("Ignoring acknowledgement %s: %s", event_id, details)

    _record_processed(
        db,
        event_id=event_id,
        event_type=event_type,
        supplier_id=supplier_id,
        occurred_at=occurred_at,
        status=outcome,
    )

    if not _commit_or_duplicate(db, event_id):
        return ProcessingResult(
            status="DUPLICATE",
            event_id=event_id,
            details=f"Event {event_id} already processed concurrently",
        )

    logger.info("PO acknowledgement %s for %s: %s", event_id, po.po_id, outcome)
    return ProcessingResult(
        status=outcome,
        event_id=event_id,
        affected_po=po.po_id,
        details=details,
    )


HEARTBEAT_FILE = Path(
    os.getenv("PO_ACKNOWLEDGED_CONSUMER_HEARTBEAT_FILE", "/tmp/po-acknowledged-consumer.heartbeat")
)


def write_heartbeat(path: Path = HEARTBEAT_FILE) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(time.time()), encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not write PO acknowledged consumer heartbeat %s: %s", path, exc)


class _SimpleTopicPartition:
    def __init__(self, topic, partition, offset):
        self.topic, self.partition, self.offset = topic, partition, offset


class POAcknowledgedConsumerWorker:
    """
    Dedicated Kafka consumer worker for supplierportal.po.acknowledged events (Flow B).

    Guarantees:
    - Dedicated consumer group: settings.PO_ACKNOWLEDGED_CONSUMER_GROUP ('inventory-po-acknowledged-consumer')
    - At-least-once delivery: Offset is committed only AFTER DB transaction commits.
    - Idempotency: ProcessedEvent deduplication.
    - Dead-letter queue (DLQ): Unparseable/invalid events routed to settings.PO_ACKNOWLEDGED_DLQ_TOPIC.
    """

    def __init__(
        self,
        consumer=None,
        dlq_publisher=None,
        db_session_factory=None,
        max_retries: int = 5,
    ):
        self._consumer = consumer
        self._dlq_publisher = dlq_publisher
        self._db_session_factory = db_session_factory
        self.max_retries = max_retries
        self._attempts: dict[tuple, int] = {}

    @property
    def consumer(self):
        if self._consumer is None:
            if Consumer is None:
                raise RuntimeError("confluent_kafka is required for live Consumer")
            self._consumer = Consumer({
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "group.id": settings.PO_ACKNOWLEDGED_CONSUMER_GROUP,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
                "socket.timeout.ms": 3000,
                "session.timeout.ms": 10000,
            })
            self._consumer.subscribe([settings.PO_ACKNOWLEDGED_TOPIC])
        return self._consumer

    @property
    def dlq_publisher(self):
        if self._dlq_publisher is None:
            from app.services.kafka_producer import KafkaEventPublisher
            self._dlq_publisher = KafkaEventPublisher()
        return self._dlq_publisher

    @property
    def db_session_factory(self):
        if self._db_session_factory is None:
            from app.database import SessionLocal
            self._db_session_factory = SessionLocal
        return self._db_session_factory

    def route_to_dlq(
        self,
        raw_message: str,
        error_reason: str,
        topic: str,
        partition: int = 0,
        offset: int = 0,
    ) -> None:
        dlq_payload = {
            "raw_message": raw_message,
            "error": error_reason,
            "failed_at": datetime.now(UTC).isoformat(),
            "consumer_group": settings.PO_ACKNOWLEDGED_CONSUMER_GROUP,
            "topic": topic,
            "partition": partition,
            "offset": offset,
        }
        logger.error(
            "Routing bad message to DLQ topic '%s': %s",
            settings.PO_ACKNOWLEDGED_DLQ_TOPIC,
            error_reason,
        )
        try:
            ok = self.dlq_publisher.publish(
                topic=settings.PO_ACKNOWLEDGED_DLQ_TOPIC,
                key=f"{topic}-{partition}-{offset}",
                value=json.dumps(dlq_payload),
            )
        except Exception as exc:
            raise DeadLetterPublishError(f"DLQ publish failed: {exc}") from exc
        if ok is False:
            raise DeadLetterPublishError("DLQ publisher reported failure")

    def commit_offset(self, msg) -> None:
        if hasattr(self.consumer, "commit"):
            try:
                self.consumer.commit(message=msg, asynchronous=False)
            except TypeError:
                self.consumer.commit(msg)

    def _rewind(self, msg, attempt: int) -> None:
        if TopicPartition is not None or hasattr(self.consumer, "seek"):
            tp_cls = TopicPartition or _SimpleTopicPartition
            self.consumer.seek(tp_cls(msg.topic(), msg.partition(), msg.offset()))
        time.sleep(min(settings.PO_ACKNOWLEDGED_CONSUMER_INTERVAL_SECONDS * attempt, 30.0))

    def handle_kafka_message(
        self,
        db: Session,
        msg: Any,
    ) -> ProcessingResult:
        topic = getattr(msg, "topic", lambda: settings.PO_ACKNOWLEDGED_TOPIC)()
        partition = getattr(msg, "partition", lambda: 0)()
        offset = getattr(msg, "offset", lambda: 0)()

        raw_val = msg.value() if hasattr(msg, "value") else msg
        if isinstance(raw_val, bytes):
            raw_text = raw_val.decode("utf-8", errors="replace")
        elif isinstance(raw_val, str):
            raw_text = raw_val
        else:
            raw_text = str(raw_val)

        try:
            event_data = json.loads(raw_text)
            if not isinstance(event_data, dict):
                raise InvalidMessageError("Event payload must be a JSON object")
        except json.JSONDecodeError as exc:
            err_msg = f"Unparseable JSON message: {exc}"
            self.route_to_dlq(raw_text, err_msg, topic, partition, offset)
            self.commit_offset(msg)
            return ProcessingResult(status="DLQ", event_id="", details=err_msg)
        except InvalidMessageError as exc:
            self.route_to_dlq(raw_text, str(exc), topic, partition, offset)
            self.commit_offset(msg)
            return ProcessingResult(status="DLQ", event_id="", details=str(exc))

        try:
            result = process_po_acknowledged_event(db=db, event_data=event_data)
        except InvalidMessageError as exc:
            db.rollback()
            self.route_to_dlq(raw_text, str(exc), topic, partition, offset)
            self.commit_offset(msg)
            return ProcessingResult(
                status="DLQ",
                event_id=event_data.get("event_id", ""),
                details=str(exc),
            )
        except Exception as exc:
            db.rollback()
            logger.error("Transient error processing event: %s. Offset will NOT be committed.", exc)
            raise

        self.commit_offset(msg)
        return result

    def run_worker_loop(
        self,
        poll_timeout: float = 1.0,
        stop_event=None,
        max_messages: Optional[int] = None,
    ) -> int:
        processed_count = 0
        logger.info(
            "Starting PO Acknowledged Consumer Worker (topic=%s, group=%s)...",
            settings.PO_ACKNOWLEDGED_TOPIC,
            settings.PO_ACKNOWLEDGED_CONSUMER_GROUP,
        )

        while True:
            if stop_event is not None and stop_event.is_set():
                logger.info("Stopping PO Acknowledged Consumer Worker...")
                break

            msg = self.consumer.poll(timeout=poll_timeout)
            if msg is None:
                write_heartbeat()
                continue

            if hasattr(msg, "error") and msg.error():
                err = msg.error()
                if not (KafkaError and err.code() == KafkaError._PARTITION_EOF):
                    logger.error("Kafka consumer error: %s", err)
                write_heartbeat()
                continue

            key = (msg.topic(), msg.partition(), msg.offset())
            db = self.db_session_factory()
            try:
                self.handle_kafka_message(db, msg)
                self._attempts.pop(key, None)
                processed_count += 1
            except Exception as exc:
                attempt = self._attempts.get(key, 0) + 1
                self._attempts[key] = attempt
                if attempt >= self.max_retries:
                    logger.error(
                        "Processing repeatedly failed (%d attempts) at %s[%s]@%s: %s. Routing to DLQ.",
                        attempt,
                        *key,
                        exc,
                    )
                    raw_val = msg.value() if hasattr(msg, "value") else msg
                    raw_text = raw_val.decode("utf-8", errors="replace") if isinstance(raw_val, bytes) else str(raw_val)
                    try:
                        self.route_to_dlq(
                            raw_message=raw_text,
                            error_reason=f"Exceeded max retries ({self.max_retries}): {exc}",
                            topic=key[0],
                            partition=key[1],
                            offset=key[2],
                        )
                        self.commit_offset(msg)
                        self._attempts.pop(key, None)
                        processed_count += 1
                    except Exception as dlq_err:
                        logger.critical("Could not route failed message to DLQ: %s", dlq_err)
                        self._rewind(msg, attempt)
                else:
                    logger.error(
                        "Processing failed (attempt %d/%d) at %s[%s]@%s: %s. Rewinding to retry.",
                        attempt,
                        self.max_retries,
                        *key,
                        exc,
                    )
                    self._rewind(msg, attempt)
            finally:
                db.close()

            write_heartbeat()
            if max_messages is not None and processed_count >= max_messages:
                break

        return processed_count


def run_po_acknowledged_consumer(poll_timeout: float = 1.0, stop_event=None) -> None:
    """Entry point for the standalone PO acknowledged consumer worker."""
    worker = POAcknowledgedConsumerWorker()
    worker.run_worker_loop(poll_timeout=poll_timeout, stop_event=stop_event)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_po_acknowledged_consumer()


