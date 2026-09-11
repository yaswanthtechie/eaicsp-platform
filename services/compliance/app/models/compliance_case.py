from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)

from app.core.database import Base


class ComplianceCase(Base):

    __tablename__ = "compliance_case"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    case_number = Column(
        String,
        nullable=False,
        unique=True,
        index=True,
    )

    entity_name = Column(
        String,
        nullable=False,
        index=True,
    )

    entity_type = Column(
        String,
        nullable=False,
    )

    country = Column(
        String,
        nullable=True,
        index=True,
    )

    matched_name = Column(
        String,
        nullable=True,
    )

    matched_lists = Column(
        String,
        nullable=True,
    )

    match_score = Column(
        Integer,
        nullable=False,
        default=0,
    )

    risk_score = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    screening_tier = Column(
        String,
        nullable=True,
    )

    screening_action = Column(
        String,
        nullable=True,
    )

    status = Column(
        String,
        nullable=False,
        default="OPEN",
        index=True,
    )

    assigned_to = Column(
        String,
        nullable=True,
        index=True,
    )

    assigned_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    resolution = Column(
        String,
        nullable=True,
    )

    resolution_reason = Column(
        Text,
        nullable=True,
    )

    resolved_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )