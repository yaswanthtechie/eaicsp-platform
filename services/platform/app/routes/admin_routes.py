from fastapi import APIRouter, Depends

from app.core.dependencies import require_role
from app.schemas.user import UserResponse

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"]
)


@router.get(
    "/test",
    response_model=UserResponse
)

def admin_test(
    user=Depends(
        require_role(
            "ceo",
            "vp_operations",
            

        )
    )
):
    return {
        "message": "Admin access granted",
        "user": user
    }
