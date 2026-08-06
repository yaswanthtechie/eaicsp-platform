from sqlalchemy.orm import Session

from app.models.audit import ComplianceAudit


def write_audit(
    db: Session,
    entity_name: str,
    result: dict,
    service_name: str,
    duration_ms: float,
):
    """
    Store one screening event.
    """

    audit = ComplianceAudit(

        entity_name=entity_name,

        matched=result["is_flagged"],

        matched_name=result["matched_name"],

        matched_lists=",".join(
            result["matched_lists"]
        ),

        match_score=result["match_score"],

        service_name=service_name,

        duration_ms=duration_ms,

    )

    db.add(audit)

    db.commit()

    db.refresh(audit)

    return audit


def get_audit_history(
    db: Session,
    entity_name: str,
):
    """
    Return all screenings for one entity.
    """

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