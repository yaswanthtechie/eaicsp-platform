from datetime import UTC, datetime
from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.compliance_event import ProcessedEvent, SupplierComplianceState
from app.models.purchase_order import PurchaseOrder

try:
    from confluent_kafka import Consumer, KafkaError, KafkaException
except ImportError:
    Consumer = None
    KafkaError = None
    KafkaException = None

logger = logging.getLogger(__name__)


class InvalidMessageError(Exception):
    """Raised when an incoming Kafka message is malformed, unparseable, or violates schema."""


@dataclass
class ProcessingResult:
    status: str  # "PROCESSED", "DUPLICATE", "OUT_OF_ORDER", "DLQ"
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


def process_compliance_event(db: Session, event_data: dict[str, Any]) -> ProcessingResult:
    """
    Core business logic for reacting to compliance.supplier.status_changed event.
    Guarantees:
    1. Idempotency: Duplicate event_ids leave state untouched.
    2. Out-of-order safety: Older events do not regress newer states.
    3. Purchase Order actions: Draft POs are held on block/review and released on clear.
    """
    # 1. Envelope validations
    event_id = event_data.get("event_id")
    event_type = event_data.get("event_type")
    event_version = event_data.get("event_version")
    occurred_at_raw = event_data.get("occurred_at")
    payload = event_data.get("payload")

    if not event_id or not isinstance(event_id, str):
        raise InvalidMessageError("Missing or invalid 'event_id' in event envelope")

    if not event_type or not isinstance(event_type, str):
        raise InvalidMessageError("Missing or invalid 'event_type' in event envelope")

    if str(event_version) != "1.0":
        raise InvalidMessageError(f"Unknown or unsupported event_version: '{event_version}' (expected '1.0')")

    if not payload or not isinstance(payload, dict):
        raise InvalidMessageError("Missing or invalid 'payload' object in event envelope")

    # 2. Payload validations
    supplier_id = payload.get("supplier_id")
    new_status = payload.get("new_status")
    reason = payload.get("reason") or "Compliance status changed"

    if not supplier_id or not isinstance(supplier_id, str):
        raise InvalidMessageError("Missing or invalid 'supplier_id' in payload")

    if not new_status or not isinstance(new_status, str):
        raise InvalidMessageError("Missing or invalid 'new_status' in payload")

    classified = classify_compliance_status(new_status)
    if classified is None:
        raise InvalidMessageError(f"Unknown compliance status in payload: '{new_status}'")

    try:
        occurred_at = parse_iso_datetime(occurred_at_raw)
    except Exception as exc:
        raise InvalidMessageError(f"Invalid 'occurred_at' timestamp: {occurred_at_raw}") from exc

    # 3. Idempotency check: Have we processed this event_id already?
    existing_event = db.query(ProcessedEvent).filter(ProcessedEvent.event_id == event_id).first()
    if existing_event is not None:
        logger.info(
            "Event %s has already been processed at %s with status %s. Skipping.",
            event_id,
            existing_event.processed_at,
            existing_event.status,
        )
        return ProcessingResult(
            status="DUPLICATE",
            event_id=event_id,
            affected_pos=[],
            details=f"Event {event_id} already processed",
        )

    # 4. Out-of-order check: Is this event older than the supplier's latest recorded event?
    state = (
        db.query(SupplierComplianceState)
        .filter(SupplierComplianceState.supplier_id == supplier_id)
        .first()
    )

    if state is not None:
        state_ts = state.last_occurred_at
        if state_ts.tzinfo is None:
            state_ts = state_ts.replace(tzinfo=UTC)
        else:
            state_ts = state_ts.astimezone(UTC)

        if occurred_at < state_ts:
            logger.warning(
                "Out-of-order event %s for supplier %s (occurred_at %s < last_occurred_at %s). "
                "Event ignored to prevent stale state regression.",
                event_id,
                supplier_id,
                occurred_at,
                state_ts,
            )
            # Record processed event as SKIPPED_OUT_OF_ORDER to maintain idempotency
            processed_record = ProcessedEvent(
                event_id=event_id,
                event_type=event_type,
                supplier_id=supplier_id,
                occurred_at=occurred_at,
                status="SKIPPED_OUT_OF_ORDER",
                processed_at=datetime.now(UTC),
            )
            db.add(processed_record)
            db.commit()

            return ProcessingResult(
                status="OUT_OF_ORDER",
                event_id=event_id,
                affected_pos=[],
                details=f"Out-of-order event: timestamp {occurred_at} is older than last known {state_ts}",
            )

    # 5. Business mutation: Hold or Release Draft POs
    affected_pos = []

    if classified in {"BLOCKED", "NEEDS_REVIEW"}:
        # When supplier moves to blocked or needs review: every open draft PO must be put on hold
        draft_pos = (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.supplier_id == supplier_id,
                PurchaseOrder.status == "draft",
            )
            .all()
        )
        for po in draft_pos:
            po.status = "on_hold"
            po.hold_reason = reason
            affected_pos.append(po.po_id)

        logger.info(
            "Supplier %s moved to %s (%s). Placed %d draft POs on hold.",
            supplier_id,
            new_status,
            classified,
            len(affected_pos),
        )

    elif classified == "CLEARED":
        # When cleared again: released back to draft
        held_pos = (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.supplier_id == supplier_id,
                PurchaseOrder.status == "on_hold",
            )
            .all()
        )
        for po in held_pos:
            po.status = "draft"
            po.hold_reason = None
            affected_pos.append(po.po_id)

        logger.info(
            "Supplier %s cleared. Released %d held POs back to draft.",
            supplier_id,
            len(affected_pos),
        )

    # 6. Update SupplierComplianceState
    try:
        if state is None:
            state = SupplierComplianceState(
                supplier_id=supplier_id,
                last_status=new_status,
                last_occurred_at=occurred_at,
                last_event_id=event_id,
                last_reason=reason,
                updated_at=datetime.now(UTC),
            )
            db.add(state)
        else:
            state.last_status = new_status
            state.last_occurred_at = occurred_at
            state.last_event_id = event_id
            state.last_reason = reason
            state.updated_at = datetime.now(UTC)

        # 7. Record ProcessedEvent
        processed_record = ProcessedEvent(
            event_id=event_id,
            event_type=event_type,
            supplier_id=supplier_id,
            occurred_at=occurred_at,
            status="PROCESSED",
            processed_at=datetime.now(UTC),
        )
        db.add(processed_record)

        # 8. Commit database write
        db.commit()
    except Exception:
        db.rollback()
        raise

    return ProcessingResult(
        status="PROCESSED",
        event_id=event_id,
        affected_pos=affected_pos,
        details=f"Successfully processed status change to {new_status} for supplier {supplier_id}",
    )


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


class ComplianceConsumerWorker:
    """
    Kafka consumer worker for compliance.supplier.status_changed events.
    
    Guarantees:
    - At-least-once delivery: Offset is committed only AFTER database write succeeds.
    - Idempotent: Same event processed twice produces no side effects.
    - Dead-letter queue (DLQ): Unparseable, unknown event_version, or malformed messages
      are routed to settings.COMPLIANCE_DLQ_TOPIC with reason, and offset is committed.
      A bad message never stops the consumer.
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
    ) -> bool:
        """Route unparseable or defective messages to the DLQ topic with the failure reason."""
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
            return self.dlq_publisher.publish(
                topic=settings.COMPLIANCE_DLQ_TOPIC,
                key=f"dlq-{int(time.time() * 1000)}",
                value=json.dumps(dlq_payload),
            )
        except Exception as exc:
            logger.error("Failed to publish bad message to DLQ topic: %s", exc)
            return False

    def commit_offset(self, msg) -> None:
        """Commit message offset after confirmed processing."""
        if hasattr(self.consumer, "commit"):
            try:
                self.consumer.commit(message=msg, asynchronous=False)
            except TypeError:
                # Some mock or client signatures use positional
                self.consumer.commit(msg)

    def handle_kafka_message(
        self,
        db: Session,
        msg: Any,
        simulate_crash_before_commit: bool = False,
    ) -> ProcessingResult:
        """
        Handle a single Kafka message end-to-end:
        1. Decode and parse message.
        2. If invalid: send to DLQ, commit offset, return DLQ result.
        3. If valid: execute process_compliance_event and commit DB transaction.
        4. If crash simulated before commit: raise exception without committing offset.
        5. If DB committed: commit Kafka offset.
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

        # Check crash-before-commit simulation
        if simulate_crash_before_commit:
            raise RuntimeError("Simulated service crash occurred after database write and before Kafka commit!")

        # Database write confirmed! Now commit the Kafka offset
        self.commit_offset(msg)
        return result

    def run_worker_loop(
        self,
        poll_timeout: float = 1.0,
        stop_event=None,
        max_messages: Optional[int] = None,
    ) -> int:
        """
        Continuous consumer loop. One bad message will never stop the consumer.
        """
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
                if KafkaError and err.code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("Kafka consumer error: %s", err)
                write_heartbeat()
                continue

            db = self.db_session_factory()
            try:
                self.handle_kafka_message(db, msg)
                processed_count += 1
            except Exception as exc:
                logger.error("Consumer worker loop error on message: %s", exc)
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
