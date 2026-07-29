from datetime import (
    datetime,
    timezone
)


from fastapi import APIRouter


from app.schemas.compliance import (
    ComplianceRequest,
    ComplianceResponse
)


from app.services.sanctions_service import (
    check_name
)



router = APIRouter()



@router.post(
    "/screen",
    response_model=ComplianceResponse
)
def screen_entity(
    request: ComplianceRequest
):


    result = check_name(
        request.entity_name
    )



    return ComplianceResponse(

        **result,

        checked_at=datetime.now(
            timezone.utc
        ).isoformat()

    )