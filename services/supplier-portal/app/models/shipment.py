from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    JSON,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.database import Base


class Shipment(Base):
    __tablename__ = "shipments"
    __table_args__ = {"schema": settings.SUPPLIER_DB_SCHEMA}

    shipment_id: Mapped[str] = mapped_column(
        String(20), primary_key=True
    )
    po_number: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )
    supplier_id: Mapped[str] = mapped_column(
        String(9), nullable=False, index=True
    )

    shipment_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )
    expected_delivery_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )
    carrier: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    tracking_number: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    origin: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    destination_warehouse: Mapped[str] = mapped_column(
        String(10), nullable=False
    )
    items: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="created"
    )
    created_by: Mapped[str] = mapped_column(
        String(100), nullable=False
    )

    dispatched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    eta_days: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    confidence_low: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    confidence_high: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    model_version: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    predicted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    top_features: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
