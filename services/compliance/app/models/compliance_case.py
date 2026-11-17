from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ComplianceCase(Base):
    __tablename__ = "compliance_case"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_number: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True
    )
    entity_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    normalized_entity_name: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    matched_name: Mapped[str | None] = mapped_column(String, nullable=True)
    matched_lists: Mapped[str | None] = mapped_column(String, nullable=True)
    match_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    screening_tier: Mapped[str | None] = mapped_column(String, nullable=True)
    screening_action: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="OPEN", index=True
    )
    assigned_to: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution: Mapped[str | None] = mapped_column(String, nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
