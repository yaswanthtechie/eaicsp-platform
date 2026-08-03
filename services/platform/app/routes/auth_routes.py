
from fastapi import APIRouter , HTTPException,Depends, Request,status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError

from app.core.config import TRUST_PROXY
from app.services.auth_service import login_user,users
from app.schemas.auth import (
    TokenResponse,
    RefreshRequest,
    AccessTokenResponse,
)
from app.core.security import (
    create_access_token,
    decode_token,
)
router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"]
)

def get_client_ip(request: Request) -> str:
# Only trust X-Forwarded-For when we are actually behind a proxy we control.
# Otherwise any caller can forge it and reset their own rate-limit bucket.
    if TRUST_PROXY:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

@router.post(
"/login",
response_model=TokenResponse
)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    return login_user(
        username=form_data.username,
        password=form_data.password,
        client_ip=get_client_ip(request)
    )


@router.post(
"/refresh",
response_model=AccessTokenResponse
)

def refresh_token(body: RefreshRequest):
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
       raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token"
    )
    if  payload.get("type") != "refresh":
        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token"
    )

    user = users.get(payload.get("sub"))

    if user is None or not user["is_active"]:
        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid user"
    )

    new_access_token = create_access_token(
        {
            "sub": user["email"],
            "user_id": user["user_id"],
            "role": user["role"].value
        }
)

    return {
    "access_token": new_access_token,
    "token_type": "bearer"
}


