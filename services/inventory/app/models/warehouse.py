from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
)

from app.database import Base


class Warehouse(Base):
    __tablename__ = "warehouses"

    warehouse_id = Column(
        String(16),
        primary_key=True,
        index=True,
    )

    name = Column(
        String(255),
        nullable=False,
    )

    city = Column(
        String(64),
        nullable=False,
    )

    state = Column(
        String(64),
        nullable=False,
    )

    country = Column(
        String(64),
        nullable=False,
        default="India",
    )

    pincode = Column(
        String(16),
        nullable=True,
    )

    lat = Column(
        Float,
        nullable=True,
    )

    lng = Column(
        Float,
        nullable=True,
    )

    capacity_units = Column(
        Integer,
        nullable=False,
    )

    demand_weight = Column(
        Float,
        nullable=False,
        default=1.0,
    )

    warehouse_type = Column(
        String(32),
        nullable=False,
        default="central",
    )

    parent_warehouse_id = Column(
        String(16),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
