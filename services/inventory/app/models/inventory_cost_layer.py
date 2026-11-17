from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InventoryCostLayer(Base):
    __tablename__ = "inventory_cost_layers"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    sku_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    warehouse_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    category: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    quantity_received: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    quantity_remaining: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_cost: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
