from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.dependencies import require_role
from app.schemas.user import UserResponse

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"]
)

class AdminTestResponse(BaseModel):
    message:str
    user:UserResponse

@router.get(
    "/test",
    response_model=AdminTestResponse
)

def admin_test(user=Depends(require_role("ceo","vp_operations"))):
    return {
        "message": "Admin access granted",
        "user": {
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.name,
            "is_active": user.is_active,
        }
    }


       

