from fastapi import (
    APIRouter,
    Depends,
    Query,
)

from sqlalchemy.orm import Session

from app.core.database import get_db

from app.schemas.compliance import (
    ComplianceRequest,
    ComplianceResponse,
    BulkComplianceRequest,
    BulkComplianceResponse,
)

from app.services.sanctions_service import (
    screen_entity,
    screen_bulk,
)

from app.services.audit_service import (
    write_audit,
    write_bulk_audit,
    get_audit_history,
)


router = APIRouter()


@router.post(
    "/screen",
    response_model=ComplianceResponse,
)
def screen(
    request: ComplianceRequest,
    db: Session = Depends(get_db),
):
    """
    Screen one entity against the sanctions lists.
    """

    result = screen_entity(
        request.entity_name
    )

    result["entity_name"] = request.entity_name
    result["entity_type"] = request.entity_type
    result["country"] = request.country

    write_audit(
        db=db,
        entity_name=request.entity_name,
        result=result,
        duration_ms=result["duration_ms"],
    )

    return result


@router.post(
    "/screen-bulk",
    response_model=BulkComplianceResponse,
)
def bulk_screen(
    request: BulkComplianceRequest,
    db: Session = Depends(get_db),
):
   

    bulk_result = screen_bulk(
        request.entity_names
    )

    results = []

    for entity_name, result in zip(
        request.entity_names,
        bulk_result["results"],
    ):
        result["entity_name"] = entity_name
        result["entity_type"] = request.entity_type
        result["country"] = request.country

        results.append(result)

    write_bulk_audit(
        db=db,
        entity_names=request.entity_names,
        results=results,
    )

    return {
        "entity_type": request.entity_type,
        "country": request.country,
        "count": bulk_result["count"],
        "total_duration_ms": bulk_result[
            "total_duration_ms"
        ],
        "results": results,
    }

@router.get(
    "/audit"
)
def audit_history(
    entity_name: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Get audit history for an entity.

    Example:
        GET /audit?entity_name=HAMAS
    """

    return get_audit_history(
        db=db,
        entity_name=entity_name,
    )