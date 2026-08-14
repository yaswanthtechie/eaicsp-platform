from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Index,
)

from app.core.database import Base



class ComplianceAudit(Base):

    __tablename__ = "compliance_audit"


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


    matched = Column(

        Boolean,

        nullable=False,

        default=False,

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


    service_name = Column(

        String,

        nullable=False,

    )


    duration_ms = Column(

        Float,

        nullable=False,

    )


    created_at = Column(

        DateTime(
            timezone=True
        ),

        nullable=False,

        default=lambda: datetime.now(
            timezone.utc
        ),

        index=True,

    )


    __table_args__ = (

        Index(
            "idx_audit_entity_date",
            "entity_name",
            "created_at",
        ),

    )