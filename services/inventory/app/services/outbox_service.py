from datetime import UTC, datetime
import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.outbox import Outbox
from app.schemas.events import EventEnvelope
from app.core.config import settings

logger = logging.getLogger(__name__)


def record_event(
    db: Session,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    trace_id: Optional[str] = None,
) -> Outbox:
    """
    Transactional Outbox Writer:
    Writes an event envelope into the outbox table within the caller's active database transaction.
    
    IMPORTANT: This function does NOT commit the transaction.
    The caller commits so that the business mutation and event are committed atomically.
    If the transaction rolls back, the event is also rolled back and never published.
    """
    envelope = EventEnvelope(
        event_type=event_type,
        payload=payload,
        trace_id=trace_id,
    )

    serialized_payload = envelope.model_dump_json()

    outbox_entry = Outbox(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=serialized_payload,
        status="PENDING",
    )

    db.add(outbox_entry)
    logger.debug(
        "Recorded outbox event %s for %s (%s)",
        event_type,
        aggregate_type,
        aggregate_id,
    )
    return outbox_entry


def get_pending_events(
    db: Session,
    limit: int = 50,
) -> list[Outbox]:
    """
    Pending and retryable events. New events (retry_count 0) come first,
    so a pile of failing events can never starve them. DEAD events are
    never picked up again.
    """
    return (
        db.query(Outbox)
        .filter(Outbox.status.in_(["PENDING", "FAILED"]))
        .order_by(Outbox.retry_count.asc(), Outbox.created_at.asc())
        .limit(limit)
        .all()
    )


def mark_published(
    db: Session,
    outbox_id: str,
) -> None:
    """Mark an outbox event as successfully published."""
    entry = db.query(Outbox).filter(Outbox.id == outbox_id).first()
    if entry:
        entry.status = "PUBLISHED"
        entry.published_at = datetime.now(UTC)
        db.commit()


def mark_failed(
    db: Session,
    outbox_id: str,
    error: str,
    is_broker_error: bool = False,
) -> None:
    """
    Record a failed publish.

    Correctness guarantees:
    - Broker outages NEVER dead-letter events. An event must remain FAILED (retryable)
      as long as the failure is due to broker downtime or network issues, no matter
      how many polls or seconds the outage lasts (satisfies docs/events.md:54).
    - The retry cap (OUTBOX_MAX_RETRIES) applies ONLY to failures caused by the event
      itself (poison pills, oversized payloads, invalid schema). Such events become DEAD
      after max retries so they do not block subsequent traffic.
    """
    entry = db.query(Outbox).filter(Outbox.id == outbox_id).first()
    if entry is None:
        return

    entry.retry_count += 1
    entry.last_error = error[:2000]

    if not is_broker_error and entry.retry_count >= settings.OUTBOX_MAX_RETRIES:
        entry.status = "DEAD"
        logger.error(
            "Outbox event %s (%s) dead-lettered after %d attempts: %s",
            entry.id,
            entry.event_type,
            entry.retry_count,
            entry.last_error,
        )
    else:
        entry.status = "FAILED"

    db.commit()
