
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.compliance_case import ComplianceCase
from app.models.case_history import CaseHistory
from app.services.case_state_machine import (
    CASE_OPEN,
    CASE_UNDER_REVIEW,
    CASE_CLEARED,
    CASE_CONFIRMED,
    validate_transition,
)


def _next_case_number(db: Session) -> str:
    last_case = (
        db.query(ComplianceCase)
        .order_by(
            ComplianceCase.id.desc()
        )
        .first()
    )

    next_id = (
        last_case.id + 1
        if last_case
        else 1
    )

    return f"CASE-{next_id:06d}"


def create_case(
    db: Session,
    entity_name: str,
    entity_type: str,
    country: str,
    result: dict,
) -> ComplianceCase:

    existing_case = (
        db.query(ComplianceCase)
        .filter(
            ComplianceCase.entity_name.ilike(
                entity_name.strip()
            ),
            ComplianceCase.status.in_(
                [
                    CASE_OPEN,
                    CASE_UNDER_REVIEW,
                ]
            ),
        )
        .first()
    )

    if existing_case:
        return existing_case

    matched_lists = result.get(
        "matched_lists",
        [],
    ) or []

    if isinstance(matched_lists, list):
        matched_lists = ",".join(
            str(item)
            for item in matched_lists
            if item
        )

    case = ComplianceCase(
        case_number=_next_case_number(db),
        entity_name=entity_name.strip(),
        entity_type=entity_type,
        country=(
            country.strip()
            if country
            else None
        ),
        matched_name=result.get(
            "matched_name"
        ),
        matched_lists=matched_lists,
        match_score=int(
            result.get(
                "match_score",
                0,
            )
            or 0
        ),
        risk_score=float(
            result.get(
                "risk_score",
                0.0,
            )
            or 0.0
        ),
        screening_tier=result.get(
            "screening_tier"
        ),
        screening_action=result.get(
            "screening_action"
        ),
        status=CASE_OPEN,
    )

    db.add(case)
    db.commit()
    db.refresh(case)

    history = CaseHistory(
        case_id=case.id,
        from_status=None,
        to_status=CASE_OPEN,
        changed_by="system",
        reason="Flagged screening created case",
    )

    db.add(history)
    db.commit()

    return case


def transition_case(
    db: Session,
    case: ComplianceCase,
    new_status: str,
    changed_by: str = "system",
    reason: str | None = None,
    comments: str | None = None,
) -> ComplianceCase:

    validate_transition(
        current_status=case.status,
        new_status=new_status,
    )

    old_status = case.status

    case.status = new_status
    case.updated_at = datetime.now(
        timezone.utc
    )

    if new_status in {
        CASE_CLEARED,
        CASE_CONFIRMED,
    }:
        case.resolution = new_status
        case.resolution_reason = reason
        case.resolved_at = datetime.now(
            timezone.utc
        )

    history = CaseHistory(
        case_id=case.id,
        from_status=old_status,
        to_status=new_status,
        changed_by=changed_by,
        reason=reason,
        comments=comments,
    )

    db.add(case)
    db.add(history)
    db.commit()
    db.refresh(case)

    return case


def assign_case(
    db: Session,
    case: ComplianceCase,
    assigned_to: str,
    changed_by: str = "system",
) -> ComplianceCase:

    case.assigned_to = assigned_to.strip()
    case.assigned_at = datetime.now(
        timezone.utc
    )
    case.updated_at = datetime.now(
        timezone.utc
    )

    history = CaseHistory(
        case_id=case.id,
        from_status=case.status,
        to_status=case.status,
        changed_by=changed_by,
        reason="Case assigned",
        comments=f"Assigned to {assigned_to}",
    )

    db.add(case)
    db.add(history)
    db.commit()
    db.refresh(case)

    return case


def review_case(
    db: Session,
    case: ComplianceCase,
    reviewer: str,
    decision: str,
    reason: str,
    comments: str | None = None,
) -> ComplianceCase:
    """
    Internal case-review workflow.

    Flow:

        OPEN
          ↓
        UNDER_REVIEW
          ↓
        CLEARED / CONFIRMED

    The case is assigned to the reviewer,
    moved into review, and then resolved.
    """

    decision = decision.upper().strip()

    if decision not in {
        CASE_CLEARED,
        CASE_CONFIRMED,
    }:
        raise ValueError(
            "Decision must be CLEARED or CONFIRMED"
        )

    if case.status != CASE_OPEN:
        raise ValueError(
            f"Case must be OPEN before review. "
            f"Current status: {case.status}"
        )

    # Step 1: Assign the case to the reviewer.
    assign_case(
        db=db,
        case=case,
        assigned_to=reviewer,
        changed_by=reviewer,
    )

    # Step 2: Start the review.
    transition_case(
        db=db,
        case=case,
        new_status=CASE_UNDER_REVIEW,
        changed_by=reviewer,
        reason="Case review started",
        comments=comments,
    )

    # Step 3: Complete the review.
    transition_case(
        db=db,
        case=case,
        new_status=decision,
        changed_by=reviewer,
        reason=reason,
        comments=comments,
    )

    return case

