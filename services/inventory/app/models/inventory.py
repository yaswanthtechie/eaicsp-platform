from sqlalchemy import (
    Float,
    Integer,
    PrimaryKeyConstraint,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Inventory(Base):
    __tablename__ = "inventory"

    sku_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    warehouse_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    product_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    category: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="Uncategorized",
    )

    quantity_on_hand: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # R4 compatibility.
    # Actual demand is calculated from SalesHistory.
    avg_daily_demand: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    lead_time_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    safety_stock: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reorder_point: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # =====================================================
    # MILESTONE 1 - MULTI-ECHELON
    # =====================================================

    warehouse_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="local",
    )

    parent_warehouse_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "sku_id",
            "warehouse_id",
        ),
    )
