from datetime import UTC, datetime, timedelta
from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.compliance_event import ProcessedEvent, SupplierComplianceState
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier

try:
    from confluent_kafka import Consumer, KafkaError, KafkaException, TopicPartition
except ImportError:
    Consumer = None
    KafkaError = None
    KafkaException = None
    TopicPartition = None

logger = logging.getLogger(__name__)

EVENT_TYPE = "compliance.supplier.status_changed"
SUPPORTED_EVENT_VERSIONS = {1}            # matches EVENT_VERSION in the compliance producer
MAX_FUTURE_SKEW = timedelta(minutes=5)    # tolerate small clock drift, nothing more


class InvalidMessageError(Exception):
    """Raised when an incoming Kafka message is malformed, unparseable, or violates schema."""


class DeadLetterPublishError(Exception):
    """Raised when a bad message could not be written to the DLQ (so its offset must not be committed)."""


@dataclass
class ProcessingResult:
    status: str  # "PROCESSED", "DUPLICATE", "OUT_OF_ORDER", "UNKNOWN_SUPPLIER", "DLQ"
    event_id: str
    affected_pos: list[str] = field(default_factory=list)
    details: str = ""


def classify_compliance_status(status_str: Optional[str]) -> Optional[str]:
    """
    Classify compliance status strings into canonical actions:
    - BLOCKED: supplier is confirmed blocked or sanctions match
    - NEEDS_REVIEW: supplier requires human compliance review
    - CLEARED: supplier has been cleared
    """
    if not status_str or not isinstance(status_str, str):
        return None

    normalized = status_str.strip().lower().replace("-", "_").replace(" ", "_")

    if normalized in {"block", "blocked", "confirmed"}:
        return "BLOCKED"
    if normalized in {"review", "needs_review", "under_review", "open"}:
        return "NEEDS_REVIEW"
    if normalized in {"clear", "cleared"}:
        return "CLEARED"

    return None


def parse_iso_datetime(dt_str: Any) -> datetime:
    """Parse ISO8601 string to timezone-aware UTC datetime."""
    if not isinstance(dt_str, str):
        raise ValueError(f"Expected ISO datetime string, got {type(dt_str)}")

    # Replace trailing 'Z' with '+00:00' for standard fromisoformat parsing
    normalized = dt_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt


def resolve_supplier_id(db: Session, payload: dict[str, Any]) -> Optional[str]:
    """
    The compliance event identifies a supplier by name (it has no supplier_id).
    Prefer supplier_id if the producer ever adds it; otherwise look the name up.
    Returns None if inventory has no such supplier.
    """
    supplier_id = payload.get("supplier_id")
    if isinstance(supplier_id, str) and supplier_id:
        return supplier_id

    name = payload.get("supplier_name")
    if not isinstance(name, str) or not name.strip():
        raise InvalidMessageError("Missing 'supplier_name' (and no 'supplier_id') in payload")

    matches = (
        db.query(Supplier.supplier_id)
        .filter(func.lower(func.trim(Supplier.supplier_name)) == name.strip().lower())
        .all()
    )
    if len(matches) > 1:
        raise InvalidMessageError(
            f"Ambiguous supplier_name {name!r}: matches {sorted(m[0] for m in matches)}"
        )
    return matches[0][0] if matches else None


def _record_processed(db: Session, *, event_id, event_type, supplier_id, occurred_at, status) -> None:
    db.add(ProcessedEvent(
        event_id=event_id,
        event_type=event_type,
        supplier_id=supplier_id,
        occurred_at=occurred_at,
        status=status,
        processed_at=datetime.now(UTC),
    ))


def _commit_or_duplicate(db: Session, event_id: str) -> bool:
    """
    Commit the transaction. Returns False if a concurrent delivery of the same
    event_id committed first (primary-key race), which means "duplicate", not "error".
    """
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        if db.query(ProcessedEvent).filter(ProcessedEvent.event_id == event_id).first() is not None:
            return False
        raise
    except Exception:
        db.rollback()
        raise


def _duplicate(event_id: str) -> ProcessingResult:
    return ProcessingResult(status="DUPLICATE", event_id=event_id,
                            details=f"Event {event_id} already processed")


def process_compliance_event(db: Session, event_data: dict[str, Any]) -> ProcessingResult:
    """
    React to compliance.supplier.status_changed.
    1. Idempotency: duplicate event_ids leave state untouched.
    2. Out-of-order safety: older events never regress newer state.
    3. BLOCK/REVIEW -> open draft POs put on hold; CLEAR -> released back to draft.
    The idempotency record, the PO changes and the supplier state commit together.
    """
    # 1. Envelope
    event_id = event_data.get("event_id")
    event_type = event_data.get("event_type")
    event_version = event_data.get("event_version")
    payload = event_data.get("payload")

    if not isinstance(event_id, str) or not event_id:
        raise InvalidMessageError("Missing or invalid 'event_id' in event envelope")
    if event_type != EVENT_TYPE:
        raise InvalidMessageError(f"Unexpected event_type {event_type!r} (expected {EVENT_TYPE!r})")
    if isinstance(event_version, bool) or event_version not in SUPPORTED_EVENT_VERSIONS:
        raise InvalidMessageError(
            f"Unknown or unsupported event_version: {event_version!r} "
            f"(supported: {sorted(SUPPORTED_EVENT_VERSIONS)})"
        )
    if not isinstance(payload, dict) or not payload:
        raise InvalidMessageError("Missing or invalid 'payload' object in event envelope")

    # 2. Payload
    new_status = payload.get("new_status")
    if not isinstance(new_status, str) or not new_status:
        raise InvalidMessageError("Missing or invalid 'new_status' in payload")
    classified = classify_compliance_status(new_status)
    if classified is None:
        raise InvalidMessageError(f"Unknown compliance status in payload: '{new_status}'")
    reason = payload.get("reason") or "Compliance status changed"

    occurred_at_raw = event_data.get("occurred_at")
    try:
        occurred_at = parse_iso_datetime(occurred_at_raw)
    except Exception as exc:
        raise InvalidMessageError(f"Invalid 'occurred_at' timestamp: {occurred_at_raw}") from exc
    if occurred_at > datetime.now(UTC) + MAX_FUTURE_SKEW:
        raise InvalidMessageError(
            f"'occurred_at' {occurred_at.isoformat()} is in the future; "
            "rejected so it cannot mask later real events"
        )

    # 3. Idempotency
    existing = db.query(ProcessedEvent).filter(ProcessedEvent.event_id == event_id).first()
    if existing is not None:
        logger.info("Event %s already processed at %s (%s). Skipping.",
                    event_id, existing.processed_at, existing.status)
        return _duplicate(event_id)

    # 4. Which inventory supplier is this?
    supplier_id = resolve_supplier_id(db, payload)
    if supplier_id is None:
        logger.warning("No inventory supplier named %r; event %s recorded with no PO changes.",
                       payload.get("supplier_name"), event_id)
        _record_processed(db, event_id=event_id, event_type=event_type, supplier_id=None,
                          occurred_at=occurred_at, status="SKIPPED_UNKNOWN_SUPPLIER")
        if not _commit_or_duplicate(db, event_id):
            return _duplicate(event_id)
        return ProcessingResult(status="UNKNOWN_SUPPLIER", event_id=event_id,
                                details=f"No inventory supplier named {payload.get('supplier_name')!r}")

    # Item 8: Lock the supplier row to close the race with PO creation
    db.query(Supplier).filter(Supplier.supplier_id == supplier_id).with_for_update().first()

    # 5. Out-of-order
    state = (
        db.query(SupplierComplianceState)
        .filter(SupplierComplianceState.supplier_id == supplier_id)
        .first()
    )
    if state is not None:
        state_ts = state.last_occurred_at
        state_ts = state_ts.replace(tzinfo=UTC) if state_ts.tzinfo is None else state_ts.astimezone(UTC)
        if occurred_at < state_ts:
            logger.warning("Out-of-order event %s for supplier %s (%s < %s). Ignored.",
                           event_id, supplier_id, occurred_at, state_ts)
            _record_processed(db, event_id=event_id, event_type=event_type, supplier_id=supplier_id,
                              occurred_at=occurred_at, status="SKIPPED_OUT_OF_ORDER")
            if not _commit_or_duplicate(db, event_id):
                return _duplicate(event_id)
            return ProcessingResult(status="OUT_OF_ORDER", event_id=event_id,
                                    details=f"Event at {occurred_at} is older than last known {state_ts}")

    # 6. Hold or release
    affected_pos: list[str] = []
    if classified in {"BLOCKED", "NEEDS_REVIEW"}:
        pos = (
            db.query(PurchaseOrder)
            .filter(PurchaseOrder.supplier_id == supplier_id,
                    PurchaseOrder.status.in_(["draft", "on_hold"]))
            .all()
        )
        for po in pos:
            if po.status == "draft":
                affected_pos.append(po.po_id)
            po.status = "on_hold"
            po.hold_reason = reason          # REVIEW -> BLOCK also refreshes the reason on held POs
            po.hold_source = "compliance"    # Item 7: Record compliance as the hold source
        logger.info("Supplier %s -> %s (%s). Put %d draft POs on hold.",
                    supplier_id, new_status, classified, len(affected_pos))
    else:  # CLEARED
        held = (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.supplier_id == supplier_id,
                PurchaseOrder.status == "on_hold",
                PurchaseOrder.hold_source == "compliance",
            )
            .all()
        )
        for po in held:
            po.status = "draft"              # released, NOT sent
            po.hold_reason = None
            po.hold_source = None
            affected_pos.append(po.po_id)
        logger.info("Supplier %s cleared. Released %d POs back to draft.", supplier_id, len(affected_pos))

    # 7. Supplier state + processed event, committed with the PO changes
    now = datetime.now(UTC)
    if state is None:
        db.add(SupplierComplianceState(
            supplier_id=supplier_id, last_status=new_status, last_occurred_at=occurred_at,
            last_event_id=event_id, last_reason=reason, updated_at=now,
        ))
    else:
        state.last_status = new_status
        state.last_occurred_at = occurred_at
        state.last_event_id = event_id
        state.last_reason = reason
        state.updated_at = now

    _record_processed(db, event_id=event_id, event_type=event_type, supplier_id=supplier_id,
                      occurred_at=occurred_at, status="PROCESSED")
    if not _commit_or_duplicate(db, event_id):
        return _duplicate(event_id)

    return ProcessingResult(status="PROCESSED", event_id=event_id, affected_pos=affected_pos,
                            details=f"Processed {new_status} for supplier {supplier_id}")


HEARTBEAT_FILE = Path(
    os.getenv("COMPLIANCE_CONSUMER_HEARTBEAT_FILE", "/tmp/compliance-consumer.heartbeat")
)


def write_heartbeat(path: Path = HEARTBEAT_FILE) -> None:
    """Touch the consumer heartbeat file for Docker container healthchecks."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(time.time()), encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not write compliance consumer heartbeat %s: %s", path, exc)


class _SimpleTopicPartition:
    """Used only when confluent_kafka isn't installed (unit tests)."""
    def __init__(self, topic, partition, offset):
        self.topic, self.partition, self.offset = topic, partition, offset


class ComplianceConsumerWorker:
    """
    Kafka consumer worker for compliance.supplier.status_changed events.
    
    Guarantees:
    - At-least-once delivery: Offset is committed only AFTER database write succeeds.
    - Idempotent: Same event processed twice produces no side effects.
    - Dead-letter queue (DLQ): Unparseable, unknown event_version, or malformed messages
      are routed to settings.COMPLIANCE_DLQ_TOPIC with reason, and offset is committed.
      If DLQ publish fails, DeadLetterPublishError is raised and offset is NOT committed.
    """

    def __init__(
        self,
        consumer=None,
        dlq_publisher=None,
        db_session_factory=None,
    ):
        self._consumer = consumer
        self._dlq_publisher = dlq_publisher
        self._db_session_factory = db_session_factory
        self._attempts: dict[tuple, int] = {}

    @property
    def consumer(self):
        if self._consumer is None:
            if Consumer is None:
                raise RuntimeError("confluent_kafka is required for live Consumer")
            self._consumer = Consumer({
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "group.id": settings.KAFKA_CONSUMER_GROUP,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,  # Manual commit after confirmed DB write
                "socket.timeout.ms": 3000,
                "session.timeout.ms": 10000,
            })
            self._consumer.subscribe([settings.COMPLIANCE_STATUS_CHANGED_TOPIC])
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
        """Write a bad message to the DLQ. Raises DeadLetterPublishError if that fails."""
        dlq_payload = {
            "raw_message": raw_message,
            "error": error_reason,
            "failed_at": datetime.now(UTC).isoformat(),
            "consumer_group": settings.KAFKA_CONSUMER_GROUP,
            "topic": topic,
            "partition": partition,
            "offset": offset,
        }
        logger.error(
            "Routing bad message to DLQ topic '%s': %s",
            settings.COMPLIANCE_DLQ_TOPIC,
            error_reason,
        )
        try:
            ok = self.dlq_publisher.publish(
                topic=settings.COMPLIANCE_DLQ_TOPIC,
                key=f"{topic}-{partition}-{offset}",      # traceable back to the source message
                value=json.dumps(dlq_payload),
            )
        except Exception as exc:
            raise DeadLetterPublishError(f"DLQ publish failed: {exc}") from exc
        if ok is False:
            raise DeadLetterPublishError("DLQ publisher reported failure")

    def commit_offset(self, msg) -> None:
        """Commit message offset after confirmed processing."""
        if hasattr(self.consumer, "commit"):
            try:
                self.consumer.commit(message=msg, asynchronous=False)
            except TypeError:
                # Some mock or client signatures use positional
                self.consumer.commit(msg)

    def _rewind(self, msg, attempt: int) -> None:
        """Seek back so Kafka redelivers this exact message; back off, capped at 30s."""
        if TopicPartition is not None or hasattr(self.consumer, "seek"):
            tp_cls = TopicPartition or _SimpleTopicPartition
            self.consumer.seek(tp_cls(msg.topic(), msg.partition(), msg.offset()))
        time.sleep(min(settings.COMPLIANCE_CONSUMER_INTERVAL_SECONDS * attempt, 30.0))

    def handle_kafka_message(
        self,
        db: Session,
        msg: Any,
    ) -> ProcessingResult:
        """
        Handle a single Kafka message end-to-end:
        1. Decode and parse message.
        2. If invalid: send to DLQ (raises DeadLetterPublishError if DLQ down), commit offset, return DLQ result.
        3. If valid: execute process_compliance_event and commit DB transaction.
        4. If DB committed: commit Kafka offset.
        """
        topic = getattr(msg, "topic", lambda: settings.COMPLIANCE_STATUS_CHANGED_TOPIC)()
        partition = getattr(msg, "partition", lambda: 0)()
        offset = getattr(msg, "offset", lambda: 0)()

        # Extract message payload
        raw_val = msg.value() if hasattr(msg, "value") else msg
        if isinstance(raw_val, bytes):
            raw_text = raw_val.decode("utf-8", errors="replace")
        elif isinstance(raw_val, str):
            raw_text = raw_val
        else:
            raw_text = str(raw_val)

        # Attempt to parse JSON
        try:
            event_data = json.loads(raw_text)
            if not isinstance(event_data, dict):
                raise InvalidMessageError("Event payload must be a JSON object")
        except json.JSONDecodeError as exc:
            # Bad message: Unparseable JSON
            err_msg = f"Unparseable JSON message: {exc}"
            self.route_to_dlq(raw_text, err_msg, topic, partition, offset)
            self.commit_offset(msg)
            return ProcessingResult(status="DLQ", event_id="", details=err_msg)
        except InvalidMessageError as exc:
            # Bad message: Not a JSON object
            self.route_to_dlq(raw_text, str(exc), topic, partition, offset)
            self.commit_offset(msg)
            return ProcessingResult(status="DLQ", event_id="", details=str(exc))

        # Process the event against the database
        try:
            result = process_compliance_event(db=db, event_data=event_data)
        except InvalidMessageError as exc:
            # Bad message: unknown event_version, missing fields, invalid format
            db.rollback()
            self.route_to_dlq(raw_text, str(exc), topic, partition, offset)
            self.commit_offset(msg)
            return ProcessingResult(status="DLQ", event_id=event_data.get("event_id", ""), details=str(exc))
        except Exception as exc:
            # DB write error or infrastructure failure: DO NOT COMMIT OFFSET!
            db.rollback()
            logger.error("Transient error processing event: %s. Offset will NOT be committed.", exc)
            raise

        # Database write confirmed! Now commit the Kafka offset
        self.commit_offset(msg)
        return result

    def run_worker_loop(
        self,
        poll_timeout: float = 1.0,
        stop_event=None,
        max_messages: Optional[int] = None,
    ) -> int:
        """Continuous consumer loop. A bad message goes to the DLQ; a failure is retried, never skipped."""
        processed_count = 0
        logger.info(
            "Starting Compliance Consumer Worker (topic=%s, group=%s)...",
            settings.COMPLIANCE_STATUS_CHANGED_TOPIC,
            settings.KAFKA_CONSUMER_GROUP,
        )

        while True:
            if stop_event is not None and stop_event.is_set():
                logger.info("Stopping Compliance Consumer Worker...")
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
                logger.error(
                    "Processing failed (attempt %d) at %s[%s]@%s: %s. Rewinding to retry.",
                    attempt,
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


def run_compliance_consumer(poll_timeout: float = 1.0, stop_event=None) -> None:
    """Entry point for standalone compliance consumer worker."""
    worker = ComplianceConsumerWorker()
    worker.run_worker_loop(poll_timeout=poll_timeout, stop_event=stop_event)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_compliance_consumer()
