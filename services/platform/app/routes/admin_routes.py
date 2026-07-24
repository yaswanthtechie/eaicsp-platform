from fastapi import APIRouter, Depends

from app.core.dependencies import require_role


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"]
)


@router.get("/test")
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
