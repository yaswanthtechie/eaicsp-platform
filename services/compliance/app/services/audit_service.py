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

        matched_name=result.get(
            "matched_name"
        ),

        matched_lists=",".join(
            result.get(
                "matched_lists",
                [],
            )
        ),

        match_score=result.get(
            "match_score",
            0,
        ),

        service_name=SERVICE_NAME,

        duration_ms=duration_ms,
    )

    db.add(audit)

    # Single request -> single commit
    db.commit()

    db.refresh(audit)

    return audit



def write_bulk_audit(
    db: Session,
    entity_names: list[str],
    results: list[dict],
):
    

    audits = []



    for entity_name, result in zip(
        entity_names,
        results,
    ):

        audit = ComplianceAudit(

            entity_name=entity_name,

            matched=result["is_flagged"],

            matched_name=result.get(
                "matched_name"
            ),

            matched_lists=",".join(
                result.get(
                    "matched_lists",
                    [],
                )
            ),

            match_score=result.get(
                "match_score",
                0,
            ),

            service_name=SERVICE_NAME,

            duration_ms=result.get(
                "duration_ms",
                0.0,
            ),
        )

        audits.append(audit)

    

    if audits:

        db.add_all(audits)

        db.commit()

    return audits




def get_audit_history(
    db: Session,
    entity_name: str,
):
    

    return (
        db.query(
            ComplianceAudit
        )

        .filter(
            ComplianceAudit.entity_name
            == entity_name
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