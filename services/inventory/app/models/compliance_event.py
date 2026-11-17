from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProcessedEvent(Base):
    """
    Stores processed event IDs for exactly-once idempotency semantics.
    Delivering the same event_id twice must not alter state the second time.
    """

    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )
    supplier_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        index=True,
    )
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    status: Mapped[str] = mapped_column(
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

    supplier_id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        index=True,
    )
    last_status: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    last_occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_event_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    last_reason: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
