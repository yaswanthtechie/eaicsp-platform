from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String

from app.database import Base


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    po_id = Column(String, primary_key=True, index=True)

    sku_id = Column(String, nullable=False, index=True)

    warehouse_id = Column(String, nullable=False, index=True)

    supplier_id = Column(String, nullable=False)

    quantity = Column(Integer, nullable=False)

    unit_cost = Column(Float, nullable=False)

    expected_cost = Column(Float, nullable=False)

    status = Column(
        String,
        nullable=False,
        default="draft"
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )