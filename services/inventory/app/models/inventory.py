from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    PrimaryKeyConstraint,
)

from app.database import Base


class Inventory(Base):

    __tablename__ = "inventory"

    sku_id = Column(
        String,
        nullable=False,
    )

    warehouse_id = Column(
        String,
        nullable=False,
    )

    product_name = Column(
        String,
        nullable=False,
    )
    category = Column(
    String,
    nullable=False,
    default="Uncategorized",
    )

    quantity_on_hand = Column(
        Integer,
        nullable=False,
    )

    # R4 compatibility.
    # Actual demand is calculated from SalesHistory.
    avg_daily_demand = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    lead_time_days = Column(
        Integer,
        nullable=False,
    )

    safety_stock = Column(
        Integer,
        nullable=False,
    )

    # =====================================================
    # MILESTONE 1 - MULTI-ECHELON
    # =====================================================

    warehouse_type = Column(
        String,
        nullable=False,
        default="local",
    )

    parent_warehouse_id = Column(
        String,
        nullable=True,
    )
    version = Column(
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