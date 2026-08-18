from fastapi import (
    APIRouter,
    Depends,
    Query,
    HTTPException,
)

from sqlalchemy.orm import Session

from app.core.database import get_db

from app.schemas.compliance import (
    ComplianceRequest,
    ComplianceResponse,
    BulkComplianceRequest,
    BulkComplianceResponse,
    OverrideCreateRequest,
    OverrideResponse,
)

from app.services.sanctions_service import (
    screen_entity,
    screen_bulk,
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


router = APIRouter()


@router.post(
    "/screen",
    response_model=ComplianceResponse,
)
def screen(
    request: ComplianceRequest,
    db: Session = Depends(get_db),
):
    result = screen_entity(
        name=request.entity_name,
        country=request.country,
    )

    result["entity_name"] = request.entity_name
    result["entity_type"] = request.entity_type
    result["country"] = request.country

    result["source"] = result.get(
        "matched_lists",
        [],
    )


    result["override_applied"] = False
    result["override_reason"] = None
    result["reviewed_by"] = None



    if (
        result["is_flagged"]
        and result.get("matched_name")
    ):
        matched_name = result["matched_name"]

        sources = result.get(
            "matched_lists",
            [],
        )

        for source in sources:

            override = get_override(
                db=db,
                entity_name=request.entity_name,
                matched_name=matched_name,
                source=source,
            )

            if override:

                result["is_flagged"] = False

                result["override_applied"] = True

                result["override_reason"] = (
                    override.reason
                )

                result["reviewed_by"] = (
                    override.reviewed_by
                )

                break


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
        names=request.entity_names,
        country=request.country,
    )

    results = []


    for entity_name, result in zip(
        request.entity_names,
        bulk_result["results"],
    ):

        result["entity_name"] = entity_name

        result["entity_type"] = (
            request.entity_type
        )

        result["country"] = (
            request.country
        )

        result["source"] = result.get(
            "matched_lists",
            [],
        )

        # Default override values
        result["override_applied"] = False
        result["override_reason"] = None
        result["reviewed_by"] = None



        if (
            result["is_flagged"]
            and result.get("matched_name")
        ):
            matched_name = result[
                "matched_name"
            ]

            sources = result.get(
                "matched_lists",
                [],
            )

            for source in sources:

                override = get_override(
                    db=db,
                    entity_name=entity_name,
                    matched_name=matched_name,
                    source=source,
                )

                if override:

                    result["is_flagged"] = False

                    result[
                        "override_applied"
                    ] = True

                    result[
                        "override_reason"
                    ] = override.reason

                    result[
                        "reviewed_by"
                    ] = override.reviewed_by

                    break

        results.append(result)



    write_bulk_audit(
        db=db,
        entity_names=request.entity_names,
        results=results,
    )

    return {
        "entity_type": request.entity_type,
        "country": request.country,
        "count": len(results),
        "total_duration_ms": (
            bulk_result["total_duration_ms"]
        ),
        "results": results,
    }

@router.get(
    "/audit"
)
def audit_history(
    entity_name: str = Query(...),
    db: Session = Depends(get_db),
):
    return get_audit_history(
        db=db,
        entity_name=entity_name,
    )



@router.get(
    "/audit/summary"
)
def audit_summary(
    db: Session = Depends(get_db),
):
    return get_audit_summary(db)




@router.post(
    "/override",
    response_model=OverrideResponse,
)
def add_override(
    request: OverrideCreateRequest,
    db: Session = Depends(get_db),
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