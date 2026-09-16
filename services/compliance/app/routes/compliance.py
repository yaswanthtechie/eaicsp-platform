from fastapi import (
    APIRouter,
    Depends,
    Query,
    HTTPException,
)

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependency import require_roles

from app.schemas.compliance import (
    ComplianceRequest,
    ComplianceResponse,
    BulkComplianceRequest,
    BulkComplianceResponse,
    OverrideCreateRequest,
    OverrideResponse,
    ComplianceSummaryResponse,
    CaseListResponse,
)

from app.services.audit_service import (
    write_audit,
    write_bulk_audit,
    get_audit_history,
    get_audit_summary,
)

from app.services.override_service import (
    create_override,
    get_override,
    get_all_overrides,
    delete_override,
)

from app.services.case_service import (
    assign_case,
    transition_case,
    get_case_or_404,
    get_cases,
    get_case_history,
)

from app.services.compliance_screening_service import (
    screen_and_open_case,
    screen_bulk_and_open_cases,
)

from app.services.reporting_service import (
    get_compliance_summary,
)

router = APIRouter()

def get_actor_identity(auth_data) -> str:
    user_id = auth_data.get("user_id")

    if user_id is not None:
        return str(user_id)

    email = auth_data.get("email")

    if email:
        return email

    return "unknown"

@router.post(
    "/screen",
    response_model=ComplianceResponse,
)
def screen(
    request: ComplianceRequest,
    db: Session = Depends(get_db),
    auth_data=Depends(
        require_roles("compliance_officer")
    ),
):
    result = screen_and_open_case(
        db=db,
        entity_name=request.entity_name,
        entity_type=request.entity_type,
        country=request.country,
        transaction_value=request.transaction_value,
    )

    write_audit(
        db=db,
        entity_name=request.entity_name,
        result=result,
        duration_ms=result.get(
            "duration_ms",
            0,
        ),
    )

    return result

@router.post(
    "/screen-bulk",
    response_model=BulkComplianceResponse,
)
def bulk_screen(
    request: BulkComplianceRequest,
    db: Session = Depends(get_db),
    auth_data=Depends(
        require_roles("compliance_officer")
    ),
):
    results = screen_bulk_and_open_cases(
        db=db,
        entity_names=request.entity_names,
        entity_type=request.entity_type,
        country=request.country,
        transaction_value=request.transaction_value,
    )

    write_bulk_audit(
        db=db,
        entity_names=request.entity_names,
        results=results["results"],
    )

    return results

@router.get(
    "/audit",
)
def audit_history(
    entity_name: str = Query(...),
    db: Session = Depends(get_db),
    auth_data=Depends(
        require_roles("compliance_officer")
    ),
):
    return get_audit_history(
        db=db,
        entity_name=entity_name,
    )

@router.get(
    "/audit/summary",
)
def audit_summary(
    db: Session = Depends(get_db),
    auth_data=Depends(
        require_roles("compliance_officer")
    ),
):
    return get_audit_summary(db)

@router.post(
    "/override",
    response_model=OverrideResponse,
)
def add_override(
    request: OverrideCreateRequest,
    db: Session = Depends(get_db),
    auth_data=Depends(
        require_roles("compliance_officer")
    ),
):
    override = create_override(
        db=db,
        entity_name=request.entity_name,
        matched_name=request.matched_name,
        source=request.source,
        reason=request.reason,
        reviewed_by=request.reviewed_by,
    )

    return override

@router.get(
    "/override",
    response_model=OverrideResponse,
)
def read_override(
    entity_name: str = Query(...),
    matched_name: str = Query(...),
    source: str = Query(...),
    db: Session = Depends(get_db),
    auth_data=Depends(
        require_roles("compliance_officer")
    ),
):
    override = get_override(
        db=db,
        entity_name=entity_name,
        matched_name=matched_name,
        source=source,
    )

    if not override:
        raise HTTPException(
            status_code=404,
            detail="Override not found",
        )

    return override

@router.get(
    "/overrides",
    response_model=list[OverrideResponse],
)
def read_all_overrides(
    db: Session = Depends(get_db),
    auth_data=Depends(
        require_roles("compliance_officer")
    ),
):
    return get_all_overrides(db)

@router.delete(
    "/override",
)
def remove_override(
    entity_name: str = Query(...),
    matched_name: str = Query(...),
    source: str = Query(...),
    db: Session = Depends(get_db),
    auth_data=Depends(
        require_roles("compliance_officer")
    ),
):
    deleted = delete_override(
        db=db,
        entity_name=entity_name,
        matched_name=matched_name,
        source=source,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Override not found",
        )

    return {
        "message": "Override removed",
        "entity_name": entity_name,
        "matched_name": matched_name,
        "source": source,
    }

@router.get(
    "/reports/compliance-summary",
    response_model=ComplianceSummaryResponse,
)
def compliance_summary(
    db: Session = Depends(get_db),
    auth_data=Depends(
        require_roles("compliance_officer")
    ),
):
    return get_compliance_summary(db)

@router.get(
    "/cases",
    response_model=CaseListResponse,
)
def list_cases(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    auth_data=Depends(
        require_roles("compliance_officer")
    ),
):
    try:
        cases = get_cases(
            db=db,
            status=status,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return {
        "cases": cases,
        "count": len(cases),
    }

@router.get(
    "/cases/{case_number}",
)
def get_case(
    case_number: str,
    db: Session = Depends(get_db),
    auth_data=Depends(
        require_roles("compliance_officer")
    ),
):
    try:
        case = get_case_or_404(
            db=db,
            case_number=case_number,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    return case

@router.post(
    "/cases/{case_number}/assign",
)
def assign_case_to_officer(
    case_number: str,
    assigned_to: str = Query(...),
    db: Session = Depends(get_db),
    auth_data=Depends(
        require_roles("compliance_officer")
    ),
):
    try:
        case = get_case_or_404(
            db=db,
            case_number=case_number,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    try:
        return assign_case(
            db=db,
            case=case,
            assigned_to=assigned_to,
            changed_by=get_actor_identity(auth_data),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

@router.post(
    "/cases/{case_number}/status",
)
def update_case_status(
    case_number: str,
    new_status: str = Query(...),
    reason: str | None = Query(None),
    comments: str | None = Query(None),
    db: Session = Depends(get_db),
    auth_data=Depends(
        require_roles("compliance_officer")
    ),
):
    try:
        case = get_case_or_404(
            db=db,
            case_number=case_number,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    try:
        return transition_case(
            db=db,
            case=case,
            new_status=new_status.strip().upper(),
            changed_by=get_actor_identity(auth_data),
            reason=reason,
            comments=comments,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

@router.get(
    "/cases/{case_number}/history",
)
def get_case_history_route(
    case_number: str,
    db: Session = Depends(get_db),
    auth_data=Depends(
        require_roles("compliance_officer")
    ),
):
    try:
        case = get_case_or_404(
            db=db,
            case_number=case_number,
        )

        return get_case_history(
            db=db,
            case=case,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )
