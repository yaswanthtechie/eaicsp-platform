from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

RESERVATION_STATUSES = ("ACTIVE", "COMMITTED", "RELEASED", "EXPIRED")


class StockReservation(Base):
    """Database record for stock reservations supporting concurrency-safe allocation."""

    __tablename__ = "stock_reservations"

    reservation_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: uuid4().hex,
    )

    sku_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    warehouse_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="ACTIVE",
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    inventory = relationship(
        "Inventory",
        back_populates="reservations",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["sku_id", "warehouse_id"],
            ["inventory.sku_id", "inventory.warehouse_id"],
            ondelete="CASCADE",
            name="fk_stock_reservations_inventory",
        ),
        CheckConstraint(
            "quantity > 0",
            name="ck_stock_reservations_quantity_positive",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'COMMITTED', 'RELEASED', 'EXPIRED')",
            name="ck_stock_reservations_status",
        ),
        Index(
            "ix_stock_reservations_sku_warehouse_status",
            "sku_id",
            "warehouse_id",
            "status",
        ),
        Index(
            "ix_stock_reservations_status_expires_at",
            "status",
            "expires_at",
        ),
    )
