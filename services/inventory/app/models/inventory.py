from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    PrimaryKeyConstraint,
    Index,
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

    quantity_on_hand = Column(
        Integer,
        nullable=False,
    )

    # Kept for R3/database compatibility.
    # R4 calculates demand dynamically
    # from SalesHistory.
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

    __table_args__ = (

        PrimaryKeyConstraint(
            "sku_id",
            "warehouse_id",
        ),

        Index(
            "ix_inventory_sku_warehouse_quantity",
            "sku_id",
            "warehouse_id",
            "quantity_on_hand",
        ),
    )