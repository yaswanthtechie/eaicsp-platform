from datetime import UTC, datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"

    receipt_id = Column(
        String,
        primary_key=True,
        index=True,
    )

    po_id = Column(
        String,
        nullable=False,
        index=True,
    )

    supplier_id = Column(
        String,
        nullable=False,
        index=True,
    )

    warehouse_id = Column(
        String,
        nullable=False,
        index=True,
    )

    received_by = Column(
        String,
        nullable=False,
    )

    received_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    status = Column(
        String,
        nullable=False,
        default="received",
    )

    notes = Column(
        Text,
        nullable=True,
    )

    items = relationship(
        "GoodsReceiptItem",
        back_populates="receipt",
        cascade="all, delete-orphan",
        lazy="joined",
    )


class GoodsReceiptItem(Base):
    __tablename__ = "goods_receipt_items"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    receipt_id = Column(
        String,
        ForeignKey("goods_receipts.receipt_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sku_id = Column(
        String,
        nullable=False,
        index=True,
    )

    quantity_received = Column(
        Integer,
        nullable=False,
    )

    unit_cost = Column(
        Float,
        nullable=True,
    )

    receipt = relationship(
        "GoodsReceipt",
        back_populates="items",
    )

