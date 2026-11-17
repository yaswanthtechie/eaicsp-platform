from datetime import UTC, date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        index=True,
    )

    supplier_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    sku_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    unit_cost: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    lead_time_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )


class SupplierLeadTime(Base):
    """Per-(supplier_id, sku_id) lead times imported from client staging."""

    __tablename__ = "supplier_lead_times"

    supplier_id: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("suppliers.supplier_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sku_id: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("products.sku_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    average_lead_time_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    minimum_lead_time_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    maximum_lead_time_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    effective_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "supplier_id",
            "sku_id",
            name="pk_supplier_lead_times",
        ),
    )
