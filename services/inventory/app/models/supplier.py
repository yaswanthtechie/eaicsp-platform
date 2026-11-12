from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
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


class SupplierLeadTime(Base):
    """Per-(supplier_id, sku_id) lead times imported from client staging."""

    __tablename__ = "supplier_lead_times"

    supplier_id = Column(
        String(32),
        ForeignKey("suppliers.supplier_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sku_id = Column(
        String(32),
        ForeignKey("products.sku_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    average_lead_time_days = Column(
        Integer,
        nullable=False,
    )

    minimum_lead_time_days = Column(
        Integer,
        nullable=True,
    )

    maximum_lead_time_days = Column(
        Integer,
        nullable=True,
    )

    effective_date = Column(
        Date,
        nullable=True,
    )

    updated_at = Column(
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
