from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IdempotencyRecord(Base):
    """Stores HTTP idempotency keys, request hashes, and cached responses."""

    __tablename__ = "idempotency_records"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: uuid4().hex,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    scope: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    request_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="IN_PROGRESS",
    )

    response_status_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    response_body: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            "scope",
            name="uq_idempotency_key_scope",
        ),
        CheckConstraint(
            "status IN ('IN_PROGRESS', 'COMPLETED')",
            name="ck_idempotency_records_status",
        ),
        Index(
            "ix_idempotency_records_expires_at",
            "expires_at",
        ),
    )
