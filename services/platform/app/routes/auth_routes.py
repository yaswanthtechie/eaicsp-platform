from datetime import datetime, timedelta, timezone
from fastapi import APIRouter , HTTPException,Depends, Request,status,Header
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from app.core.config import TRUST_PROXY
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.users import User
from app.core.verify_rate_limiter import verify_rate_limiter
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
from app.core.token_cache import token_cache
from app.core.permissions import ROLE_PERMISSIONS
from app.core.service_auth import verify_service_api_key
from app.schemas.auth import VerifyResponse
from app.schemas.auth import (
    TokenResponse,  
    RefreshRequest,
    AccessTokenResponse,
    LogoutRequest,
    RegisterRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
   
)

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token
)
from app.core.dependencies import(
    get_current_user,
    oauth2_scheme
)
import logging
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

    permissions = ROLE_PERMISSIONS.get(role, set())

    return {
        "role": role,
        "permissions": sorted(list(permissions)),
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
# SERVICE-VERIFY
# ============================================================

logger = logging.getLogger("platform.request")

@router.post("/service-verify")
def service_verify(
    service=Depends(verify_service_api_key),
):
    return {
        "authenticated": True,
        "service": service["service"],
        "auth_type": service["auth_type"],
    }

# ============================================================
# VERIFY
# ============================================================
@router.post(
    "/verify",
    response_model=VerifyResponse,
)
def verify_access_token(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    x_caller_service: str | None = Header(
        default=None,
        alias="X-Caller-Service",
    ),
):
    
    # The header identifies the calling service for per-service rate
    # limiting. It is optional: callers that omit it share an "unknown"
    # bucket rather than being rejected, so /verify keeps its Round 5
    # contract (200 on a valid token, 401 on an invalid one).
    caller_service = (
        x_caller_service.strip().lower()
        if x_caller_service and x_caller_service.strip()
        else "unknown"
    )
    
    if not verify_rate_limiter.check(caller_service):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many /verify requests for this service. Try again later.",
        )
    
    # -------------------------------------------------
    # Check cache BEFORE JWT decode and DB query
    # -------------------------------------------------
    cached_response = token_cache.get(token)

    if cached_response is not None:
        logger.info(
            "Token verification cache HIT"
        )
        return cached_response

    logger.info(
        "Token verification cache MISS"
    )

    # -------------------------------------------------
    # Cache miss -> decode JWT
    # -------------------------------------------------
    try:
        payload = decode_token(token)

        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        email = payload.get("sub")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        email = email.lower()

    except HTTPException:
        raise

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    # -------------------------------------------------
    # DB lookup only on cache MISS
    # -------------------------------------------------
    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if user.email.lower() != email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    # -------------------------------------------------
    # locked users cannot verify existing tokens
    # -------------------------------------------------
    if user.locked_until is not None:
        locked_until = user.locked_until

        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(
                tzinfo=timezone.utc
            )

        if locked_until > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

    # -------------------------------------------------
    # include fine-grained permissions
    # -------------------------------------------------
    role = (
        user.role.name
        if user.role
        else None
    )
    permissions = sorted(
        ROLE_PERMISSIONS.get(role, set())
    )

    response_data = {
        "valid": True,
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": role,
        "supplier_id": user.supplier_id,
        "is_active": user.is_active,
        "permissions": permissions,
    }

    # -------------------------------------------------
    # JWT expiration when calculating TTL
    # -------------------------------------------------
    cache_ttl = 60

    exp = payload.get("exp")

    if exp is not None:
        remaining_seconds = int(
            exp - datetime.now(timezone.utc).timestamp()
        )

        if remaining_seconds <= 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        cache_ttl = min(60, remaining_seconds)

    token_cache.set(
        token,
        response_data,
        user_id=user.id,
        ttl_seconds=cache_ttl,
    )
    return response_data
