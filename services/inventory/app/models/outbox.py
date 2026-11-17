from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Outbox(Base):
    __tablename__ = "outbox"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: uuid4().hex,
    )

    event_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    aggregate_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    aggregate_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    payload: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="PENDING",
        index=True,
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
