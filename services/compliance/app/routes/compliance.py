from datetime import datetime, timezone

from fastapi import APIRouter

from app.schemas.compliance import (
    ComplianceRequest,
    ComplianceResponse,
)

from app.services.sanctions_service import (
    check_name,
)

router = APIRouter(
    prefix="/api/v1/compliance",
    tags=["Compliance"],
)


@router.post(
    "/screen",
    response_model=ComplianceResponse,
)
def screen_entity(
    request: ComplianceRequest,
):

    result = check_name(
        request.entity_name
    )

    return ComplianceResponse(

        is_flagged=result["is_flagged"],

        matched_lists=result["matched_lists"],

        matched_name=result["matched_name"],

        match_score=result["match_score"],

        checked_at=datetime.now(
            timezone.utc
        ).isoformat()

    )