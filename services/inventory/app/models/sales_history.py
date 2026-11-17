from datetime import date

from sqlalchemy import (
    Date,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SalesHistory(Base):
    __tablename__ = "sales_history"

    sku_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    warehouse_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    sale_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    quantity_sold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "sku_id",
            "warehouse_id",
            "sale_date",
        ),
        Index(
            "ix_sales_history_sale_date",
            "sale_date",
        ),
    )
