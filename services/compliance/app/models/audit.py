from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
)

from datetime import datetime

from app.core.database import Base


class ComplianceAudit(Base):

    __tablename__ = "compliance_audit"


    id = Column(
        Integer,
        primary_key=True,
        index=True
    )


    entity_name = Column(
        String,
        nullable=False
    )


    matched = Column(
        Boolean,
        default=False
    )


    matched_name = Column(
        String,
        nullable=True
    )


    matched_lists = Column(
        String,
        nullable=True
    )


    match_score = Column(
        Integer,
        default=0
    )


    service_name = Column(
        String,
        nullable=False
    )


    duration_ms = Column(
        Float,
        nullable=False
    )


    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )