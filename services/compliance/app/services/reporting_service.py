from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.audit import ComplianceAudit
from app.models.compliance_case import ComplianceCase


def get_compliance_summary(db: Session) -> dict:
    # Total number of screenings
    screening_volume = (
        db.query(func.count(ComplianceAudit.id))
        .scalar()
        or 0
    )

    # Total flagged screenings
    flagged_count = (
        db.query(func.count(ComplianceAudit.id))
        .filter(ComplianceAudit.matched.is_(True))
        .scalar()
        or 0
    )

    # Flag rate
    if screening_volume > 0:
        flag_rate = (
            flagged_count / screening_volume
        ) * 100
    else:
        flag_rate = 0.0

    # Open cases
    open_cases = (
        db.query(func.count(ComplianceCase.id))
        .filter(
            ComplianceCase.status.in_(
                ["OPEN", "UNDER_REVIEW"]
            )
        )
        .scalar()
        or 0
    )

    # Average resolution time
    resolved_cases = (
        db.query(ComplianceCase)
        .filter(
            ComplianceCase.status.in_(
                ["CLEARED", "CONFIRMED"]
            ),
            ComplianceCase.created_at.isnot(None),
            ComplianceCase.resolved_at.isnot(None),
        )
        .all()
    )

    if resolved_cases:
        total_resolution_seconds = sum(
            (
                case.resolved_at - case.created_at
            ).total_seconds()
            for case in resolved_cases
        )

        average_resolution_time_hours = (
            total_resolution_seconds
            / len(resolved_cases)
            / 3600
        )
    else:
        average_resolution_time_hours = 0.0

    return {
        "screening_volume": screening_volume,
        "flagged_count": flagged_count,
        "flag_rate": round(flag_rate, 2),
        "open_cases": open_cases,
        "average_resolution_time_hours": round(
            average_resolution_time_hours,
            2,
        ),
    }