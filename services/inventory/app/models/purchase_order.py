from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    po_id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        index=True,
    )

    sku_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    warehouse_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    supplier_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_cost: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    expected_cost: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="draft",
    )

    approval_status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="pending_vp_approval",
    )

    hold_reason: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    hold_source: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    order_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    expected_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    received_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
