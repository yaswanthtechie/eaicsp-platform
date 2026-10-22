from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    token: Mapped[str] = mapped_column(
        String(512), unique=True, nullable=False, index=True
    )
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
