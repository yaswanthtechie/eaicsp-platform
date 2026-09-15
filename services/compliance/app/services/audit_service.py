import json

from sqlalchemy import Integer, func
from sqlalchemy.orm import Session

from app.core.config import SERVICE_NAME
from app.models.audit import ComplianceAudit


def _build_audit_values(
    entity_name: str,
    result: dict,
    duration_ms: float = 0.0,
    screening_type: str = "INITIAL",
    newly_flagged: bool = False,
    screening_run_id: str | None = None,
) -> dict:
    


    country = result.get("country")

    if country:
        country = str(country).strip()



    country_risk_score = float(
        result.get(
            "country_risk_score",
            0.0,
        )
        or 0.0
    )


    risk_factors = dict(
        result.get(
            "risk_factors",
            {},
        )
        or {}
    )

  
    risk_factors["country_risk"] = country_risk_score


    matched_lists = result.get(
        "matched_lists",
        [],
    ) or []

    if isinstance(matched_lists, str):
        matched_lists_value = matched_lists

    else:
        matched_lists_value = ",".join(
            str(source).strip()
            for source in matched_lists
            if source
        )


    return {
       
        "entity_name": entity_name,

        "country": country,

        
        "matched": bool(
            result.get(
                "is_flagged",
                False,
            )
        ),

        "matched_name": result.get(
            "matched_name"
        ),

        "matched_lists": matched_lists_value,

        "match_score": int(
            result.get(
                "match_score",
                0,
            )
            or 0
        ),


        "risk_score": float(
            result.get(
                "risk_score",
                0.0,
            )
            or 0.0
        ),

        "risk_factors": json.dumps(
            risk_factors
        ),

     
        "country_risk_score": country_risk_score,


        "overall_supplier_risk": float(
            result.get(
                "overall_supplier_risk",
                0.0,
            )
            or 0.0
        ),

  
        "screening_type": screening_type,

        "newly_flagged": newly_flagged,

        "screening_run_id": screening_run_id,


        "service_name": SERVICE_NAME,

        "duration_ms": float(
            duration_ms
        ),
    }


def write_audit(
    db: Session,
    entity_name: str,
    result: dict,
    duration_ms: float,
    screening_type: str = "INITIAL",
    newly_flagged: bool = False,
    screening_run_id: str | None = None,
):
    

    audit_values = _build_audit_values(
        entity_name=entity_name,
        result=result,
        duration_ms=duration_ms,
        screening_type=screening_type,
        newly_flagged=newly_flagged,
        screening_run_id=screening_run_id,
    )

    audit = ComplianceAudit(
        **audit_values
    )

    db.add(audit)

    db.commit()

    db.refresh(audit)

    return audit




def write_bulk_audit(
    db: Session,
    entity_names: list[str],
    results: list[dict],
    screening_type: str = "INITIAL",
    newly_flagged: bool = False,
    screening_run_id: str | None = None,
):
    

    audits: list[ComplianceAudit] = []

    for entity_name, result in zip(
        entity_names,
        results,
    ):
        duration_ms = float(
            result.get(
                "duration_ms",
                0.0,
            )
            or 0.0
        )

        audit_values = _build_audit_values(
            entity_name=entity_name,
            result=result,
            duration_ms=duration_ms,
            screening_type=screening_type,
            newly_flagged=newly_flagged,
            screening_run_id=screening_run_id,
        )

        audit = ComplianceAudit(
            **audit_values
        )

        audits.append(audit)

    if audits:

        db.add_all(audits)

        db.commit()

        for audit in audits:
            db.refresh(audit)

    return audits



def get_audit_history(
    db: Session,
    entity_name: str,
):
    

    return (
        db.query(ComplianceAudit)
        .filter(
            func.lower(
                func.trim(
                    ComplianceAudit.entity_name
                )
            )
            ==
            entity_name.strip().lower()
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
        db.query(ComplianceAudit)
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




def get_latest_audits(
    db: Session,
) -> dict[str, ComplianceAudit]:


    records = (
        db.query(ComplianceAudit)
        .order_by(
            ComplianceAudit.created_at.desc(),
            ComplianceAudit.id.desc(),
        )
        .all()
    )

    latest: dict[str, ComplianceAudit] = {}

    for record in records:

        entity_key = (
            record.entity_name
            .strip()
            .upper()
        )

        if entity_key not in latest:

            latest[entity_key] = record

    return latest




def get_previously_cleared_entities(
    db: Session,
) -> list[ComplianceAudit]:
    

    latest_records = get_latest_audits(
        db
    )

    cleared_entities: list[
        ComplianceAudit
    ] = []

    for record in latest_records.values():

        if record.matched is False:

            cleared_entities.append(
                record
            )

    return cleared_entities




def get_audit_summary(
    db: Session,
):

    total_screenings = (
        db.query(
            func.count(
                ComplianceAudit.id
            )
        )
        .scalar()
        or 0
    )

  

    total_flagged = (
        db.query(
            func.count(
                ComplianceAudit.id
            )
        )
        .filter(
            ComplianceAudit.matched.is_(True)
        )
        .scalar()
        or 0
    )


    overall_flag_rate = (
        round(
            (
                total_flagged
                / total_screenings
            )
            * 100,
            2,
        )
        if total_screenings
        else 0.0
    )

    daily_stats = (
        db.query(
            func.date(
                ComplianceAudit.created_at
            ).label("day"),

            func.count(
                ComplianceAudit.id
            ).label("total"),

            func.sum(
                func.cast(
                    ComplianceAudit.matched,
                    Integer,
                )
            ).label("flagged"),
        )
        .group_by(
            func.date(
                ComplianceAudit.created_at
            )
        )
        .order_by(
            func.date(
                ComplianceAudit.created_at
            )
        )
        .all()
    )

    flag_rate_over_time = []

    for row in daily_stats:

        total = row.total or 0

        flagged = row.flagged or 0

        flag_rate = (
            round(
                (
                    flagged
                    / total
                )
                * 100,
                2,
            )
            if total
            else 0.0
        )

        flag_rate_over_time.append(
            {
                "date": str(row.day),

                "total": total,

                "flagged": flagged,

                "flag_rate": flag_rate,
            }
        )

    

    normalized_entity = (
        func.lower(
            func.trim(
                ComplianceAudit.entity_name
            )
        )
        .label("entity_name")
    )

    top_entities = (
        db.query(
            normalized_entity,

            func.count(
                ComplianceAudit.id
            ).label("count"),
        )
        .filter(
            ComplianceAudit.matched.is_(True)
        )
        .group_by(
            normalized_entity
        )
        .order_by(
            func.count(
                ComplianceAudit.id
            ).desc()
        )
        .limit(5)
        .all()
    )

    most_frequently_flagged_entities = [
        {
            "entity_name": row.entity_name.upper(),

            "count": row.count,
        }
        for row in top_entities
    ]



    newly_flagged_count = (
        db.query(
            func.count(
                ComplianceAudit.id
            )
        )
        .filter(
            ComplianceAudit.newly_flagged.is_(True)
        )
        .scalar()
        or 0
    )


    initial_screenings = (
        db.query(
            func.count(
                ComplianceAudit.id
            )
        )
        .filter(
            ComplianceAudit.screening_type
            == "INITIAL"
        )
        .scalar()
        or 0
    )



    rescreenings = (
        db.query(
            func.count(
                ComplianceAudit.id
            )
        )
        .filter(
            ComplianceAudit.screening_type
            == "RESCREEN"
        )
        .scalar()
        or 0
    )

    country_stats = (
        db.query(
            ComplianceAudit.country,

            func.count(
                ComplianceAudit.id
            ).label("screenings"),

            func.sum(
                func.cast(
                    ComplianceAudit.matched,
                    Integer,
                )
            ).label("flagged"),
        )
        .filter(
            ComplianceAudit.country.isnot(None)
        )
        .group_by(
            ComplianceAudit.country
        )
        .order_by(
            func.count(
                ComplianceAudit.id
            ).desc()
        )
        .all()
    )

    country_summary = []

    for row in country_stats:

        total = row.screenings or 0

        flagged = row.flagged or 0

        flag_rate = (
            round(
                (
                    flagged
                    / total
                )
                * 100,
                2,
            )
            if total
            else 0.0
        )

        country_summary.append(
            {
                "country": row.country,

                "screenings": total,

                "flagged": flagged,

                "flag_rate": flag_rate,
            }
        )


    return {
        "total_screenings":
            total_screenings,

        "total_flagged":
            total_flagged,

        "overall_flag_rate":
            overall_flag_rate,

        "newly_flagged":
            newly_flagged_count,

        "initial_screenings":
            initial_screenings,

        "rescreenings":
            rescreenings,

        "flag_rate_over_time":
            flag_rate_over_time,

        "most_frequently_flagged_entities":
            most_frequently_flagged_entities,

        "country_summary":
            country_summary,
    }