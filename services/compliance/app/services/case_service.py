from uuid import uuid4
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


def normalize_case_name(entity_name: str) -> str:
    
    normalized = " ".join(
        entity_name.strip().upper().split()
    )

    replacements = {
        "CORPORATION": "CORP",
        "COMPANY": "CO",
        "LIMITED": "LTD",
        "INCORPORATED": "INC",
        "&": "AND",
    }

    for old, new in replacements.items():
        normalized = normalized.replace(
            old,
            new,
        )

    return normalized


def create_case(
    db: Session,
    entity_name: str,
    entity_type: str,
    country: str,
    result: dict,
) -> ComplianceCase:

    normalized_name = normalize_case_name(entity_name)

    normalized_country = (
        country.strip().upper()
        if country
        else None
    )

    existing_case = (
        db.query(ComplianceCase)
        .filter(
            ComplianceCase.normalized_entity_name
            == normalized_name,
            ComplianceCase.country
            == normalized_country,
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
        case_number=f"PENDING-{uuid4().hex}",
        entity_name=entity_name.strip(),
        normalized_entity_name=normalized_name,
        entity_type=entity_type,
        country=normalized_country,
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

    # Let the database assign the primary key first.
    db.add(case)
    db.flush()

    # Generate the case number from the database-assigned ID.
    case.case_number = f"CASE-{case.id:06d}"
    db.flush()

    db.commit()
    db.refresh(case)

    # Create the initial case-history entry.
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

    # Closing a case requires a reason.
    if new_status in {
        CASE_CLEARED,
        CASE_CONFIRMED,
    }:
        if not reason or not reason.strip():
            raise ValueError(
                "Resolution reason is required when closing a case"
            )

        case.resolution = new_status
        case.resolution_reason = reason.strip()
        case.resolved_at = datetime.now(
            timezone.utc
        )

    case.status = new_status
    case.updated_at = datetime.now(
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
    """
    Assign a case to a compliance officer.

    OPEN and UNDER_REVIEW cases can be assigned.

    CLEARED and CONFIRMED cases cannot be reassigned.

    Blank or whitespace-only assigned_to values are rejected.
    """

    # Closed cases cannot be reassigned.
    if case.status in {
        CASE_CLEARED,
        CASE_CONFIRMED,
    }:
        raise ValueError(
            "Closed cases cannot be reassigned"
        )

    assigned_to = assigned_to.strip()

    # Prevent blank assignments.
    if not assigned_to:
        raise ValueError(
            "assigned_to must not be blank"
        )

    case.assigned_to = assigned_to
    case.assigned_at = datetime.now(
        timezone.utc
    )
    case.updated_at = datetime.now(
        timezone.utc
    )

    # Assignment is an audit event, not a state transition.
    #
    # Therefore:
    # OPEN -> OPEN
    # or
    # UNDER_REVIEW -> UNDER_REVIEW
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
    Complete the case-review workflow.

    Workflow:

        OPEN
          ↓
        UNDER_REVIEW
          ↓
        CLEARED / CONFIRMED
    """

    reviewer = reviewer.strip()

    if not reviewer:
        raise ValueError(
            "reviewer must not be blank"
        )

    decision = decision.strip().upper()

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

    # Assign the case to the reviewer.
    assign_case(
        db=db,
        case=case,
        assigned_to=reviewer,
        changed_by=reviewer,
    )

    # Move the case into UNDER_REVIEW.
    transition_case(
        db=db,
        case=case,
        new_status=CASE_UNDER_REVIEW,
        changed_by=reviewer,
        reason="Case review started",
        comments=comments,
    )

    # Resolve the case.
    #
    # transition_case() will reject an empty reason.
    transition_case(
        db=db,
        case=case,
        new_status=decision,
        changed_by=reviewer,
        reason=reason,
        comments=comments,
    )

    return case


def get_case_or_404(
    db: Session,
    case_number: str,
) -> ComplianceCase:
    case = (
        db.query(ComplianceCase)
        .filter(
            ComplianceCase.case_number == case_number
        )
        .first()
    )

    if not case:
        raise ValueError("Case not found")

    return case

def get_cases(
    db: Session,
    status: str | None = None,
) -> list[ComplianceCase]:
    """
    Get compliance cases, optionally filtered by status.
    """

    query = db.query(ComplianceCase)

    if status:
        status = status.strip().upper()

        allowed_statuses = {
            CASE_OPEN,
            CASE_UNDER_REVIEW,
            CASE_CLEARED,
            CASE_CONFIRMED,
        }

        if status not in allowed_statuses:
            raise ValueError(
                "Invalid status. Allowed values: "
                "OPEN, UNDER_REVIEW, CLEARED, CONFIRMED"
            )

        query = query.filter(
            ComplianceCase.status == status
        )

    return (
        query
        .order_by(
            ComplianceCase.created_at.desc()
        )
        .all()
    )


def get_case_history(
    db: Session,
    case: ComplianceCase,
) -> list[CaseHistory]:
    """
    Get the audit history for a compliance case.
    """

    return (
        db.query(CaseHistory)
        .filter(
            CaseHistory.case_id == case.id
        )
        .order_by(
            CaseHistory.id.asc()
        )
        .all()
    )