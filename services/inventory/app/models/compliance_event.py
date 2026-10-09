from datetime import UTC, datetime
from sqlalchemy import Column, DateTime, String

from app.database import Base


class ProcessedEvent(Base):
    """
    Stores processed event IDs for exactly-once idempotency semantics.
    Delivering the same event_id twice must not alter state the second time.
    """
    __tablename__ = "processed_events"

    event_id = Column(
        String,
        primary_key=True,
        index=True,
    )
    event_type = Column(
        String,
        nullable=False,
        index=True,
    )
    supplier_id = Column(
        String,
        nullable=True,
        index=True,
    )
    occurred_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    processed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    status = Column(
        String,
        nullable=False,
        default="PROCESSED",
    )


class SupplierComplianceState(Base):
    """
    Tracks the latest known compliance state and occurred_at timestamp per supplier.
    Used to detect and safely ignore out-of-order events (e.g. if 'cleared' arrives
    before an older 'blocked', we use occurred_at to prevent regressing to blocked).
    """
    __tablename__ = "supplier_compliance_states"

    supplier_id = Column(
        String,
        primary_key=True,
        index=True,
    )
    last_status = Column(
        String,
        nullable=False,
    )
    last_occurred_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_event_id = Column(
        String,
        nullable=True,
    )
    last_reason = Column(
        String,
        nullable=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

