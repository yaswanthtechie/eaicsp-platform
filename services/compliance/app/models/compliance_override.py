from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.core.database import Base


class ComplianceOverride(Base):
    __tablename__ = "compliance_override"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    entity_name = Column(
        String,
        nullable=False,
        index=True,
    )

    matched_name = Column(
        String,
        nullable=False,
        index=True,
    )

    source = Column(
        String,
        nullable=False,
        index=True,
    )

    reason = Column(
        String,
        nullable=False,
    )

    reviewed_by = Column(
        String,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )