from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user

router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"]
)


@router.get("/me")
def current_user(
        user=Depends(get_current_user)
):

    return user