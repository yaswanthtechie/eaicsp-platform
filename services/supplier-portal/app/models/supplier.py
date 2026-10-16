
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = {"schema": settings.SUPPLIER_DB_SCHEMA}

    supplier_id: Mapped[str] = mapped_column(
        String(9), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)

    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    sanctions_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    sanctions_list: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    lead_time_days: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    payment_terms_days: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    reliability_score: Mapped[float] = mapped_column(
        Float, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
