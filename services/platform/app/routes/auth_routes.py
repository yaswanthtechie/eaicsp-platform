from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter , HTTPException,Depends, Request,status, Header
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
    save_refresh_token,
    request_password_reset,
    reset_password
)
from app.services.audit_service import (
    TOKEN_REVOKED ,
    create_audit_log,
)
from app.models.refresh_token import RefreshToken
from app.schemas.auth import (
    TokenResponse,  
    RefreshRequest,
    AccessTokenResponse,
    LogoutRequest,
    RegisterRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    TokenVerifyResponse,
)

from app.core.security import (
    create_access_token,
    create_refresh_token,
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

    new_refresh_token = create_refresh_token(
    {
        "sub": user.email,
        "user_id": user.id,
    }
)

    new_refresh_expires_at = (
    datetime.now(timezone.utc)
    + timedelta(days=7)
)

# Revoke the old refresh token.
    refresh.is_revoked = True

# Save the new refresh token.
    save_refresh_token(
    db=db,
    user_id=user.id,
    token=new_refresh_token,
    expires_at=new_refresh_expires_at,
)

    db.commit()

    return {
    "access_token": new_access_token,
    "refresh_token": new_refresh_token,
    "token_type": "bearer",
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
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    refresh = (
        db.query(RefreshToken)
        .filter(RefreshToken.token == body.refresh_token)
        .first()
    )

    if refresh is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Refresh token not found",
        )
    if refresh.user_id != current_user.id:
        raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Cannot revoke another user's session",
    )

    if refresh.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token already revoked",
        )

    refresh.is_revoked = True

    create_audit_log(
        db=db,
        event_type=TOKEN_REVOKED,
        user_id=refresh.user_id,
        details="Refresh token revoked during logout",
    )

    db.commit()

    return {
        "message": "Logged out successfully"
    }
# ============================================================
# PASSWORD REQUEST
# ============================================================
@router.post("/password-reset/request")
def password_reset_request(
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    request_password_reset(
        db=db,
        email=payload.email,
    )

    return {
        "message": "If the account exists, a password reset token has been sent."
    }

# ============================================================
# PASSWORD CONFIRM
# ============================================================
@router.post("/password-reset/reset")
def password_reset_confirm(
    payload: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    reset_password(
        db=db,
        token=payload.token,
        new_password=payload.new_password,
    )

    return {
        "message": "Password has been reset successfully."
    }


# ============================================================
# TOKEN VERIFY
# ============================================================
@router.post(
    "/verify",
    response_model=TokenVerifyResponse
)
def verify_token(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token"
        )

    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token"
        )

    token = parts[1]

    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token"
        )

    if not isinstance(payload, dict) or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token"
        )

    user_id = payload.get("user_id")
    email = payload.get("sub")

    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token"
        )

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token"
        )

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None or not user.email or user.email.lower() != str(email).lower():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token"
        )

    if user.role is None or not getattr(user.role, "name", None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token"
        )

    return {
        "valid": True,
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.name,
        "is_active": user.is_active,
    }
