from datetime import datetime, UTC
from sqlalchemy import (
    Column,
    String,
    Float,
    DateTime,
)

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    sku_id = Column(
        String(16),
        primary_key=True,
        index=True,
    )

    name = Column(
        String(255),
        nullable=False,
    )

    category = Column(
        String(64),
        nullable=False,
    )

    pack_size = Column(
        String(64),
        nullable=True,
    )

    unit_price = Column(
        Float,
        nullable=False,
    )

    unit_cost = Column(
        Float,
        nullable=False,
    )

    abc_class = Column(
        String(8),
        nullable=True,
    )

    supplier_id = Column(
        String(16),
        nullable=True,
        index=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

