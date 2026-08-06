from sqlalchemy.orm import Session

from app.models.audit import (
    ComplianceAudit,
)

from app.core.config import (
    SERVICE_NAME,
)



def write_audit(
    db: Session,
    entity_name: str,
    result: dict,
    duration_ms: float,
):

    audit = ComplianceAudit(

        entity_name=entity_name,

        matched=result["is_flagged"],

        matched_name=result["matched_name"],

        matched_lists=",".join(
            result["matched_lists"]
        ),

        match_score=result["match_score"],

        service_name=SERVICE_NAME,

        duration_ms=duration_ms,

    )

    db.add(
        audit
    )

    db.commit()

    db.refresh(
        audit
    )

    return audit



def get_audit_history(
    db: Session,
    entity_name: str,
):

    return (

        db.query(
            ComplianceAudit
        )

        .filter(
            ComplianceAudit.entity_name == entity_name
        )

        .order_by(
            ComplianceAudit.created_at.desc()
        )

        .all()

    )


def get_all_audits(
    db: Session,
):

    return (

        db.query(
            ComplianceAudit
        )

        .order_by(
            ComplianceAudit.created_at.desc()
        )

        .all()

    )



def delete_all_audits(
    db: Session,
):

    db.query(
        ComplianceAudit
    ).delete()

    db.commit()