from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.database import Base


class POAckOutbox(Base):
    __tablename__ = "po_ack_outbox"
    __table_args__ = (
        Index(
            "ix_po_ack_outbox_status_created_at",
            "status",
            "created_at",
        ),
        {"schema": settings.SUPPLIER_DB_SCHEMA},
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    message_key: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
