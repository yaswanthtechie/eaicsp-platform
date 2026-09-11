from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
)

from app.database import Base


class InventoryCostLayer(Base):

    __tablename__ = "inventory_cost_layers"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    sku_id = Column(
        String,
        nullable=False,
        index=True,
    )

    warehouse_id = Column(
        String,
        nullable=False,
        index=True,
    )

    category = Column(
        String,
        nullable=False,
        index=True,
    )

    quantity_received = Column(
        Integer,
        nullable=False,
    )

    quantity_remaining = Column(
        Integer,
        nullable=False,
    )

    unit_cost = Column(
        Float,
        nullable=False,
    )

    received_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )