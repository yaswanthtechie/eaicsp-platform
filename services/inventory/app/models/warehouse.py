from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Warehouse(Base):
    __tablename__ = "warehouses"

    warehouse_id: Mapped[str] = mapped_column(
        String(16),
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    city: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    state: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    country: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="India",
    )

    pincode: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )

    lat: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    lng: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    capacity_units: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    demand_weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )

    warehouse_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="central",
    )

    parent_warehouse_id: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
