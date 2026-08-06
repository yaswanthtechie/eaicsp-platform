
from fastapi import APIRouter , HTTPException,Depends, Request,status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from app.core.config import TRUST_PROXY
from app.services.auth_service import (
    login_user,
    users,
    get_refresh_token,
    revoke_refresh_token 
)
from app.schemas.auth import (
    TokenResponse,  
    RefreshRequest,
    AccessTokenResponse,
    LogoutRequest
   
)
from app.core.security import (
    create_access_token,
    decode_token,
)
from app.core.dependencies import(
    get_current_user,
    ROLE_HIERARCHY
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
    refresh = get_refresh_token(body.refresh_token)
    
    if refresh is None:
        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or revoked refresh token"
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

@router.get("/me/permissions")
def my_permissions(
    user=Depends(get_current_user)
):
    role = getattr(user["role"], "value", user["role"])

    return {
        "role": role,
        "permissions": sorted(
            list(
                ROLE_HIERARCHY.get(role, {role})
            )
        )
    }

@router.post("/logout")
def logout(body: LogoutRequest):

    success = revoke_refresh_token(body.refresh_token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Refresh token not found"
        )

    return {
        "message": "Logged out successfully"
    }


    
