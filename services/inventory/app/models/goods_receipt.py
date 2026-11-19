from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"

    receipt_id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        index=True,
    )

    po_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    supplier_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    warehouse_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    received_by: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="received",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    items: Mapped[list["GoodsReceiptItem"]] = relationship(
        "GoodsReceiptItem",
        back_populates="receipt",
        cascade="all, delete-orphan",
        lazy="joined",
    )


class GoodsReceiptItem(Base):
    __tablename__ = "goods_receipt_items"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    receipt_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("goods_receipts.receipt_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sku_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    quantity_received: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_cost: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    receipt: Mapped["GoodsReceipt"] = relationship(
        "GoodsReceipt",
        back_populates="items",
    )
