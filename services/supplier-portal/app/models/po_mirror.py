from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.database import Base


class POMirror(Base):
    __tablename__ = "po_mirror"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_po_mirror_event_id"),
        {"schema": settings.SUPPLIER_DB_SCHEMA},
    )

    po_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    po_number: Mapped[str | None] = mapped_column(String(30), nullable=True)

    supplier_id: Mapped[str] = mapped_column(
        String(9), nullable=False, index=True
    )
    warehouse_id: Mapped[str] = mapped_column(String(10), nullable=False)

    approval_status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    approved_by: Mapped[str] = mapped_column(String(36), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    expected_delivery_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    lines: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False
    )

    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    event_version: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    trace_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="approved", server_default="approved"
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
