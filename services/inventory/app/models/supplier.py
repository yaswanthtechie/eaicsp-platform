from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
)

from app.database import Base


class Supplier(Base):

    __tablename__ = "suppliers"

    supplier_id = Column(
        String,
        primary_key=True,
        index=True,
    )

    supplier_name = Column(
        String,
        nullable=False,
    )

    sku_id = Column(
        String,
        nullable=False,
        index=True,
    )

    unit_cost = Column(
        Float,
        nullable=False,
    )

    lead_time_days = Column(
        Integer,
        nullable=False,
    )