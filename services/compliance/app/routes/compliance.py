import logging
from fastapi import (
    APIRouter,
    Depends,
    Query,
    HTTPException,
)

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependency import (
    require_roles,
    verify_internal_caller,
)

from app.schemas.compliance import (
    ComplianceRequest,
    ComplianceResponse,
    BulkComplianceRequest,
    BulkComplianceResponse,
    OverrideCreateRequest,
    OverrideResponse,
    ComplianceSummaryResponse,
    CaseListResponse,
    InternalComplianceRequest,
    InternalComplianceResponse,
)

from app.schemas.regulatory_reporting import (
    RegulatoryReportResponse,
    RegulatoryRulesResponse,
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

from app.services.internal_compliance_service import (
    clear_internal_cache,
    perform_internal_compliance_check,
)

from app.services.regulatory_rules_service import (
    get_regulatory_rules,
    evaluate_regulatory_rules,
)

from app.services.sla_service import get_sla_status


logger = logging.getLogger(__name__)

router = APIRouter()


def get_actor_identity(auth_data) -> str:
    user_id = auth_data.get("user_id")

    if user_id is not None:
        return str(user_id)

    email = auth_data.get("email")

    if email:
        return email

    return "unknown"


# ============================================================
# SCREENING
# ============================================================


@router.post(
    "/screen",
    response_model=ComplianceResponse,
    tags=["Screening"],
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
    tags=["Screening"],
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


# ============================================================
# INTERNAL SERVICE INTEGRATION
# ============================================================
@router.post(
    "/internal-check",
    response_model=InternalComplianceResponse,
    tags=["Internal Integration"],
)
def internal_compliance_check(
    request: InternalComplianceRequest,
    db: Session = Depends(get_db),
    caller_service: str = Depends(verify_internal_caller),
):
   
    logger.info(
        "Internal compliance request received: "
        "caller=%s supplier_id=%s",
        caller_service,
        request.supplier_id,
    )

    try:
        result = perform_internal_compliance_check(
            db=db,
            supplier_id=request.supplier_id,
            company_name=request.company_name,
            country=request.country,
            caller_service=caller_service,
        )

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Internal compliance check failed: "
            "caller=%s supplier_id=%s",
            caller_service,
            request.supplier_id,
        )

        raise HTTPException(
            status_code=503,
            detail="Compliance service unavailable",
        )

    logger.info(
        "Internal compliance response returned: "
        "caller=%s supplier_id=%s decision=%s "
        "cleared=%s",
        caller_service,
        request.supplier_id,
        result.get("decision"),
        result.get("cleared"),
    )

    return result
# ============================================================
# AUDIT
# ============================================================


@router.get(
    "/audit",
    tags=["Audit"],
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
    tags=["Audit"],
)
def audit_summary(
    db: Session = Depends(get_db),
    auth_data=Depends(
        require_roles("compliance_officer")
    ),
):
    return get_audit_summary(db)


# ============================================================
# OVERRIDES
# ============================================================


@router.post(
    "/override",
    response_model=OverrideResponse,
    tags=["Overrides"],
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

    clear_internal_cache()

    return override


@router.get(
    "/override",
    response_model=OverrideResponse,
    tags=["Overrides"],
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
    tags=["Overrides"],
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
    tags=["Overrides"],
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


# ============================================================
# CASE MANAGEMENT
# ============================================================


@router.get(
    "/cases",
    response_model=CaseListResponse,
    tags=["Cases"],
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
    tags=["Cases"],
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
    tags=["Cases"],
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
    tags=["Cases"],
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
        updated_case = transition_case(
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

    
    clear_internal_cache()

    return updated_case


@router.get(
    "/cases/{case_number}/history",
    tags=["Cases"],
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


# ============================================================
# REPORTS
# ============================================================


@router.get(
    "/reports/compliance-summary",
    response_model=ComplianceSummaryResponse,
    tags=["Reports"],
)
def compliance_summary(
    db: Session = Depends(get_db),
    auth_data=Depends(
        require_roles("compliance_officer")
    ),
):
    return get_compliance_summary(db)


@router.get(
    "/reports/regulatory/{country}",
    response_model=RegulatoryRulesResponse,
    tags=["Regulatory"],
)
def regulatory_report(
    country: str,
):
    rules = get_regulatory_rules(country)

    return {
        "country": country.strip().upper(),
        "applicable_rules": rules,
    }


@router.get(
    "/reports/regulatory/{country}/evaluate",
    response_model=RegulatoryReportResponse,
    tags=["Regulatory"],
)
def evaluate_regulatory_report(
    country: str,
    sanctions_cleared: bool = Query(...),
    kyc_verified: bool = Query(...),
    documents_complete: bool = Query(...),
    reporting_compliant: bool = Query(True),
):
    return evaluate_regulatory_rules(
        country=country,
        sanctions_cleared=sanctions_cleared,
        kyc_verified=kyc_verified,
        documents_complete=documents_complete,
        reporting_compliant=reporting_compliant,
    )



@router.get(
    "/sla",
    tags=["SLA"],
)
def sla_status():
    return get_sla_status()

