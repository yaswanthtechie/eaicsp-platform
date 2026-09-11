from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
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

    country = Column(
        String,
        nullable=True,
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


    risk_score = Column(
        Float,
        nullable=False,
        default=0,
    )



    risk_factors = Column(
        Text,
        nullable=True,
    )


    country_risk_score = Column(
        Float,
        nullable=False,
        default=0,
    )



    overall_supplier_risk = Column(
        Float,
        nullable=False,
        default=0,
    )


    screening_type = Column(
        String,
        nullable=False,
        default="INITIAL",
        index=True,
    )



    newly_flagged = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )



    screening_run_id = Column(
        String,
        nullable=True,
        index=True,
    )



    service_name = Column(
        String,
        nullable=False,
        default="compliance-service",
    )

    duration_ms = Column(
        Float,
        nullable=False,
        default=0,
    )



    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )



    __table_args__ = (


        Index(
            "idx_audit_entity_date",
            "entity_name",
            "created_at",
        ),


        Index(
            "idx_audit_screening_type_date",
            "screening_type",
            "created_at",
        ),

  
        Index(
            "idx_audit_newly_flagged_date",
            "newly_flagged",
            "created_at",
        ),

        Index(
            "idx_audit_screening_run",
            "screening_run_id",
        ),


        Index(
            "idx_audit_country",
            "country",
        ),
    )