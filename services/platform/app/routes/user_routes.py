from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user
from app.schemas.user import UserResponse
router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"]
)
@router.get(
    "/me",
    response_model=UserResponse
)

def current_user(
        user=Depends(get_current_user),
      
):
    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.name,
        "is_active": user.is_active,
    }