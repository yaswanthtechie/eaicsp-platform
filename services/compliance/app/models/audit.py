from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ComplianceAudit(Base):
    __tablename__ = "compliance_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    decision: Mapped[str | None] = mapped_column(String, nullable=True)
    matched_name: Mapped[str | None] = mapped_column(String, nullable=True)
    matched_lists: Mapped[str | None] = mapped_column(String, nullable=True)
    match_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    risk_factors: Mapped[str | None] = mapped_column(Text, nullable=True)
    country_risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    overall_supplier_risk: Mapped[float] = mapped_column(
        Float, nullable=False, default=0
    )
    screening_type: Mapped[str] = mapped_column(
        String, nullable=False, default="INITIAL", index=True
    )
    newly_flagged: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    screening_run_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    service_name: Mapped[str] = mapped_column(
        String, nullable=False, default="compliance-service"
    )
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    __table_args__ = (
        Index("idx_audit_entity_date", "entity_name", "created_at"),
        Index("idx_audit_screening_type_date", "screening_type", "created_at"),
        Index("idx_audit_newly_flagged_date", "newly_flagged", "created_at"),
        Index("idx_audit_screening_run", "screening_run_id"),
        Index("idx_audit_country", "country"),
        Index("idx_audit_decision", "decision"),
    )
