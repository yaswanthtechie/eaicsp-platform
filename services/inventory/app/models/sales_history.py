from sqlalchemy import (
    Column,
    String,
    Integer,
    Date,
    PrimaryKeyConstraint,
    Index,
)

from app.database import Base


class SalesHistory(Base):

    __tablename__ = "sales_history"

    sku_id = Column(
        String,
        nullable=False,
    )

    warehouse_id = Column(
        String,
        nullable=False,
    )

    sale_date = Column(
        Date,
        nullable=False,
    )

    quantity_sold = Column(
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