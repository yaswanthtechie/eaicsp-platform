from datetime import datetime

from sqlalchemy import DateTime, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.database import Base


class InventoryGoodsReceiptEvent(Base):
    """Persist Inventory receipt events for durable idempotency."""

    __tablename__ = "inventory_goods_receipt_events"
    __table_args__ = {"schema": settings.SUPPLIER_DB_SCHEMA}

    # Primary key prevents processing the same event twice.
    event_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    # One stored event per goods receipt: a re-sent receipt must never
    # add its quantities to the three-way match a second time.
    receipt_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        unique=True,
        index=True,
    )
    po_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    supplier_id: Mapped[str] = mapped_column(
        String(9),
        nullable=False,
        index=True,
    )
    payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
