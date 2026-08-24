
from fastapi import APIRouter , HTTPException,Depends, Request,status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from app.core.config import TRUST_PROXY
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.users import User
from app.services.auth_service import (
    register_user,
    login_user,
    get_refresh_token,
    revoke_refresh_token 
)
from app.schemas.auth import (
    TokenResponse,  
    RefreshRequest,
    AccessTokenResponse,
    LogoutRequest,
    RegisterRequest
   
)
from app.core.security import (
    create_access_token,
    decode_token
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


# ============================================================
# REGISTER
# ============================================================

@router.post("/register")
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    return register_user(
        db=db,
        request=request
    )

# ============================================================
# LOGIN
# ============================================================

@router.post(
"/login",
response_model=TokenResponse
)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    return login_user(
        db=db,
        username=form_data.username,
        password=form_data.password,
        client_ip=get_client_ip(request)
    )

# ============================================================
# REFRESH TOKEN
# ============================================================

@router.post(
    "/refresh",
    response_model=AccessTokenResponse
)
def refresh_token(
    body: RefreshRequest,
    db: Session = Depends(get_db)
):
    try:
        payload = decode_token(body.refresh_token)

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    refresh = get_refresh_token(
        db=db,
        token=body.refresh_token
    )

    if refresh is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token"
        )

    user = (
        db.query(User)
        .filter(
            User.id == refresh.user_id
        )
        .first()
    )

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user"
        )

    if user.role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user"
        )

    new_access_token = create_access_token(
        {
            "sub": user.email,
            "user_id": user.id,
            "role": user.role.name
        }
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }

# ============================================================
# PERMISSIONS
# ============================================================
@router.get("/me/permissions")
def my_permissions(
    user=Depends(get_current_user)
):
    if user.role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User role has not been assigned"
        )

    role = user.role.name

    return {
        "role": role,
        "permissions": sorted(
            list(
                ROLE_HIERARCHY.get(
                    role,
                    {role}
                )
            )
        )
    }

# ============================================================
# LOGOUT 
# ============================================================
@router.post("/logout")
def logout(
    body: LogoutRequest,
    db: Session = Depends(get_db)
):
    success = revoke_refresh_token(
        db=db,
        token=body.refresh_token
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Refresh token not found"
        )

    return {
        "message": "Logged out successfully"
    }

