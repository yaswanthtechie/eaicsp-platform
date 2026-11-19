from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    sku_id: Mapped[str] = mapped_column(
        String(16),
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    pack_size: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    unit_of_measure: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    unit_price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    unit_cost: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    abc_class: Mapped[str | None] = mapped_column(
        String(8),
        nullable=True,
    )

    supplier_id: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
