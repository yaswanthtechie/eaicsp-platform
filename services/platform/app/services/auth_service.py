#auth serv
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.password_validator import validate_password
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)

from app.models.users import User
from app.models.password_reset_tokens import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.failed_login_attempts import FailedLoginAttempt

from app.schemas.auth import RegisterRequest

from app.services.email_service import MockEmailService
from app.services.audit_service import (
    ACCOUNT_LOCKED,
    LOGIN_SUCCESS,
    LOGIN_FAILED,
    PASSWORD_RESET,
    create_audit_log,
)

import secrets
import threading
from collections import defaultdict
import logging


logger = logging.getLogger("auth_requests")


# ============================================================
# LOGIN SECURITY CONFIGURATION
# ============================================================

MAX_ATTEMPTS = 5

# Failed attempts are counted within this window
WINDOW = timedelta(minutes=15)

# Account remains locked for this duration
LOCKOUT_DURATION = timedelta(minutes=15)

RESET_TOKEN_EXPIRE_MINUTES = 15


# ============================================================
# REFRESH TOKEN
# ============================================================

def save_refresh_token(
    db: Session,
    user_id: int,
    token: str,
    expires_at: datetime,
):
    refresh = RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at,
    )

    db.add(refresh)

    return refresh


def get_refresh_token(
    db: Session,
    token: str,
):
    now = datetime.now(timezone.utc)

    return (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token == token,
            RefreshToken.is_revoked.is_(False),
            RefreshToken.expires_at > now,
        )
        .first()
    )

def get_refresh_token(
    db: Session,
    token: str,
):
    now = datetime.now(timezone.utc)

    refresh = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token == token,
            RefreshToken.is_revoked.is_(False),
            RefreshToken.expires_at > now,
        )
        .first()
    )

    if refresh is None:
        return None

    user = (
        db.query(User)
        .filter(User.id == refresh.user_id)
        .first()
    )

    if user is None:
        return None

    # Deactivated users cannot use refresh tokens
    if not user.is_active:
        return None

    return refresh

def revoke_refresh_token(
    db: Session,
    token: str,
):
    refresh = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token == token,
        )
        .first()
    )

    if refresh is None:
        return False

    refresh.is_revoked = True

    return True


# ============================================================
# FAILED LOGIN TRACKING
# ============================================================

def log_failed_login(
    db: Session,
    email: str,
    ip_address: str,
):
    failed_attempt = FailedLoginAttempt(
        email=email.lower(),
        ip_address=ip_address,
        attempted_at=datetime.now(timezone.utc),
    )

    db.add(failed_attempt)
    db.commit()


def get_recent_attempts_by_email(
    db: Session,
    email: str,
):
    cutoff = (
        datetime.now(timezone.utc)
        - WINDOW
    )

    return (
        db.query(FailedLoginAttempt)
        .filter(
            FailedLoginAttempt.email == email.lower(),
            FailedLoginAttempt.attempted_at >= cutoff,
        )
        .count()
    )


def get_recent_attempts_by_ip(
    db: Session,
    ip_address: str,
):
    cutoff = (
        datetime.now(timezone.utc)
        - WINDOW
    )

    return (
        db.query(FailedLoginAttempt)
        .filter(
            FailedLoginAttempt.ip_address == ip_address,
            FailedLoginAttempt.attempted_at >= cutoff,
        )
        .count()
    )


# ============================================================
# LOGIN RATE LIMITING
# ============================================================

def check_login_rate_limit(
    db: Session,
    email: str,
    client_ip: str,
):
    email_attempts = get_recent_attempts_by_email(
        db=db,
        email=email,
    )

    ip_attempts = get_recent_attempts_by_ip(
        db=db,
        ip_address=client_ip,
    )

    if (
        email_attempts >= MAX_ATTEMPTS
        or ip_attempts >= MAX_ATTEMPTS
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again after 15 minutes.",
        )


# ============================================================
# ACCOUNT LOCKOUT HELPER
# ============================================================

def is_account_locked(user: User):
    """
    Returns True when the account is currently locked.

    If the lock period has expired, the lock is cleared.
    """

    if not user.locked_until:
        return False

    now = datetime.now(timezone.utc)

    locked_until = user.locked_until

    # SQLite can return timezone-naive datetime values.
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(
            tzinfo=timezone.utc
        )

    if locked_until > now:
        return True

    # Lock period expired
    user.locked_until = None

    return False


# ============================================================
# RATE LIMIT LOCKS
# ============================================================

# One lock per email + IP bucket
_rate_limit_locks: dict[str, threading.Lock] = defaultdict(
    threading.Lock
)

_rate_limit_locks_guard = threading.Lock()


def _get_bucket_lock(
    email: str,
    client_ip: str,
) -> threading.Lock:

    key = f"{email}:{client_ip}"

    with _rate_limit_locks_guard:
        return _rate_limit_locks[key]


# ============================================================
# REGISTER
# ============================================================

def register_user(
    db: Session,
    request: RegisterRequest,
):
    email_address = request.email.lower()

    existing = (
        db.query(User)
        .filter(
            User.email == email_address
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists",
        )

    # Validate password before hashing
    validate_password(request.password)

    hashed_password = hash_password(
        request.password
    )

    now = datetime.now(timezone.utc)

    user = User(
        email=email_address,
        full_name=request.full_name,
        password=hashed_password,
        role_id=None,
        is_active=True,
        password_changed_at=now,
        password_expires_at=now + timedelta(days=90),
    )

    db.add(user)

    db.commit()

    db.refresh(user)

    return {
        "message": "User registered successfully"
    }


# ============================================================
# BASIC LOGIN
# ============================================================

def login(
    db: Session,
    username: str,
    password: str,
):
    username = username.lower()

    user = (
        db.query(User)
        .filter(
            User.email == username
        )
        .first()
    )

    if user is None:
        return None

    if not verify_password(
        password,
        user.password,
    ):
        return None

    return user


# ============================================================
# LOGIN
# ============================================================
def login_user(
    db: Session,
    username: str,
    password: str,
    client_ip: str,
):
    username = username.lower()

    lock = _get_bucket_lock(
        username,
        client_ip,
    )

    with lock:

        # ----------------------------------------------------
        # 1. Find user
        # ----------------------------------------------------

        user = (
            db.query(User)
            .filter(
                User.email == username
            )
            .first()
        )

        # ----------------------------------------------------
        # 2. Check account lockout FIRST
        # ----------------------------------------------------

        if user and is_account_locked(user):

            db.commit()

            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is temporarily locked. Try again later.",
            )

        # ----------------------------------------------------
        # 3. Check login rate limit
        # ----------------------------------------------------

        check_login_rate_limit(
            db=db,
            email=username,
            client_ip=client_ip,
        )

        # ----------------------------------------------------
        # 4. Validate username/password
        # ----------------------------------------------------

        password_valid = (
            user is not None
            and verify_password(
                password,
                user.password,
            )
        )

        if not password_valid:

            # Record failed attempt
            log_failed_login(
                db=db,
                email=username,
                ip_address=client_ip,
            )

            # Count attempts for this email
            attempts = get_recent_attempts_by_email(
                db=db,
                email=username,
            )

            # ------------------------------------------------
            # 5. Lock account only after MAX_ATTEMPTS
            # ------------------------------------------------

            if user and attempts >= MAX_ATTEMPTS:

                user.locked_until = (
                    datetime.now(timezone.utc)
                    + LOCKOUT_DURATION
                )

                create_audit_log(
                    db=db,
                    event_type=ACCOUNT_LOCKED,
                    user_id=user.id,
                    email=user.email,
                    ip_address=client_ip,
                    details=(
                        f"Account locked after "
                        f"{MAX_ATTEMPTS} failed login attempts"
                    ),
                )

                db.commit()

                logger.warning(
                    "Account locked | user_id=%s | email=%s | attempts=%s",
                    user.id,
                    user.email,
                    attempts,
                )

                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=(
                        "Account is temporarily locked "
                        "after multiple failed login attempts."
                    ),
                )

            # ------------------------------------------------
            # 6. Normal failed login
            # ------------------------------------------------

            create_audit_log(
                db=db,
                event_type=LOGIN_FAILED,
                user_id=user.id if user else None,
                email=username,
                ip_address=client_ip,
                details="Invalid credentials",
            )

            db.commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        # ----------------------------------------------------
        # 7. Check account active
        # ----------------------------------------------------

        if not user.is_active:

            create_audit_log(
                db=db,
                event_type=LOGIN_FAILED,
                user_id=user.id,
                email=user.email,
                ip_address=client_ip,
                details="Inactive user",
            )

            db.commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        # ----------------------------------------------------
        # 8. Check role
        # ----------------------------------------------------

        if not user.role:

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User role is not assigned",
            )

        # ----------------------------------------------------
        # 9. Check password expiry
        # ----------------------------------------------------

        now = datetime.now(timezone.utc)

        if user.password_expires_at:

            password_expires_at = user.password_expires_at

            if password_expires_at.tzinfo is None:
                password_expires_at = password_expires_at.replace(
                    tzinfo=timezone.utc
                )

            if password_expires_at <= now:

                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=(
                        "Password has expired. "
                        "Please reset your password."
                    ),
                )

        # ----------------------------------------------------
        # 10. Create access token
        # ----------------------------------------------------

        access_token = create_access_token(
            {
                "sub": user.email,
                "role": user.role.name,
                "user_id": user.id,
            }
        )

        # ----------------------------------------------------
        # 11. Create refresh token
        # ----------------------------------------------------

        refresh_token = create_refresh_token(
            {
                "sub": user.email,
                "user_id": user.id,
            }
        )

        refresh_expires_at = (
            datetime.now(timezone.utc)
            + timedelta(days=7)
        )

        save_refresh_token(
            db=db,
            user_id=user.id,
            token=refresh_token,
            expires_at=refresh_expires_at,
        )

        # ----------------------------------------------------
        # 12. Successful login audit
        # ----------------------------------------------------

        create_audit_log(
            db=db,
            event_type=LOGIN_SUCCESS,
            user_id=user.id,
            email=user.email,
            ip_address=client_ip,
            details="Login Successful",
        )

        logger.info(
            "User logged in | user_id=%s | role=%s | email=%s | endpoint=/api/v1/auth/login",
            user.id,
            user.role.name,
            user.email,
        )

        # ----------------------------------------------------
        # 13. Clear failed attempts for this email
        # ----------------------------------------------------

        db.query(FailedLoginAttempt).filter(
            FailedLoginAttempt.email == username,
        ).delete(
            synchronize_session=False,
        )

        db.commit()

        # ----------------------------------------------------
        # 14. Return tokens
        # ----------------------------------------------------

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

# ============================================================
# PASSWORD RESET REQUEST
# ============================================================

def request_password_reset(
    db: Session,
    email: str,
):
    email = email.lower()

    user = (
        db.query(User)
        .filter(
            User.email == email
        )
        .first()
    )

    if user is None:
        return

    # --------------------------------------------------------
    # Invalidate all previous unused reset tokens
    # --------------------------------------------------------

    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used.is_(False),
    ).update(
        {
            PasswordResetToken.used: True,
        },
        synchronize_session=False,
    )

    token = secrets.token_urlsafe(32)

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    )

    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at,
        used=False,
    )

    db.add(reset_token)

    db.commit()

    MockEmailService.send_password_reset_email(
        email=user.email,
        reset_token=token,
    )


# ============================================================
# PASSWORD RESET
# ============================================================

def reset_password(
    db: Session,
    token: str,
    new_password: str,
):
    reset_token = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token == token
        )
        .first()
    )

    if reset_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password reset token",
        )

    if reset_token.used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token already used",
        )

    now = datetime.now(timezone.utc)

    expires_at = reset_token.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    if expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token has expired",
        )

    user = (
        db.query(User)
        .filter(
            User.id == reset_token.user_id
        )
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password reset token",
        )

    # Validate new password
    validate_password(new_password)

    # Update password
    user.password = hash_password(new_password)

    # Update password lifecycle dates
    user.password_changed_at = now
    user.password_expires_at = (
        now + timedelta(days=90)
    )

    # Unlock account after successful password reset
    user.locked_until = None

    # Revoke all active refresh tokens
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.is_revoked.is_(False),
    ).update(
        {
            RefreshToken.is_revoked: True
        },
        synchronize_session=False,
    )

    # Mark reset token as used
    reset_token.used = True

    create_audit_log(
        db=db,
        event_type=PASSWORD_RESET,
        user_id=user.id,
        email=user.email,
        details="Password reset completed",
    )

    db.commit()

#serv_auth in core

from fastapi import Depends,HTTPException, Header,status
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.service_api_keys import ServiceAPIKey
from app.database import get_db
from app.routes.admin_routes import hash_service_api_key

import hashlib
import secrets

def generate_service_api_key() -> str:
    return "sk_" + secrets.token_urlsafe(32)

def hash_service_api_key(api_key: str) -> str:
    return hashlib.sha256(
        api_key.encode("utf-8")
    ).hexdigest()

def verify_service_api_key(
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing service API key",
        )

    key_hash = hash_service_api_key(x_api_key)

    service_key = (
        
        db.query(ServiceAPIKey)
        .filter(
            ServiceAPIKey.key_hash == key_hash,
            ServiceAPIKey.is_active.is_(True),
        )
        .first()
    )

    if service_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service API key",
        )

    now = datetime.now(timezone.utc)

    if (
        service_key.expires_at is not None
        and service_key.expires_at <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Service API key expired",
        )

    service_key.last_used_at = now
    db.commit()

    return {
        "service": service_key.service_name,
        "auth_type": "api_key",
    }

#adminroutes
from fastapi import APIRouter, Depends, HTTPException, status,Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone,timedelta
from app.database import get_db
from app.models.users import User
from app.models.roles import Role as RoleModel
from app.models.role_change_history import RoleChangeHistory

from app.schemas.user import (
    AdminCreateUserRequest,
    RoleChangeRequest,
    RoleChangeHistoryResponse,
    ForceResetPasswordRequest,
    UserResponse,

)
from app.schemas.admin import(
    AuditLogResponse, 
    SecurityDashboardResponse,
    ServiceAPIKeyResponse,
    ServiceAPIKeyCreateRequest,
    ServiceAPIKeyCreateResponse
)
from app.models.service_api_keys import ServiceAPIKey
from app.models.auth_audit_logs import AuthAuditLog
from app.services.audit_service import (
    create_audit_log,
    TOKEN_REVOKED,
    ROLE_CHANGED,
    LOGIN_FAILED,
    ACCOUNT_LOCKED
)
from app.models.refresh_token import RefreshToken
from app.schemas.auth import SessionResponse
from app.core.dependencies import require_role,get_current_user,require_any_role
from app.core.password_validator import validate_password
from app.core.security import hash_password
from app.core.service_auth import (
    generate_service_api_key,
    hash_service_api_key,
)
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
            "role": user.role.name if user.role else None,
            "is_active": user.is_active,
        }
    }

# ============================================================
# LIST USERS
# ============================================================
@router.get(
    "/users",
    response_model=list[UserResponse]
)
def list_users(
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    )
):
    users = (
        db.query(User)
        .order_by(User.id)
        .all()
    )

    return [
        {
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.name if user.role else None,
            "is_active": user.is_active,
        }
        for user in users
    ]

# ============================================================
# CREATE USER
# ============================================================

@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def create_user(
    request: AdminCreateUserRequest,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    )
):
    email = request.email.lower()
    
    existing = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )

    validate_password(request.password)
    role_id = None
    role_name = None
    if request.role is not None:

        role = (
            db.query(RoleModel)
            .filter(
                RoleModel.name == request.role.value
            )
            .first()
        )

        if role is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role"
            )

        role_id = role.id
        role_name = role.name

    user = User(
        email=email,
        full_name=request.full_name,
        password=hash_password(request.password),
        role_id=role_id,
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)


    if role_name is not None:

        history = RoleChangeHistory(
            user_id=user.id,
            old_role=None,
            new_role=role_name,
            changed_by=current_user.id,
        )

        db.add(history)
        db.commit()

    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.name if user.role else None,
        "is_active": user.is_active,
    }

# ============================================================
# DEACTIVATE USER
# ============================================================
@router.patch(
    "/users/{user_id}/deactivate",
    response_model=UserResponse
)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    )
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account"
        )

    # Deactivate account
    user.is_active = False

    # Revoke all active refresh tokens/sessions
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.is_revoked.is_(False),
    ).update(
        {
            RefreshToken.is_revoked: True
        },
        synchronize_session=False,
    )

    db.commit()
    db.refresh(user)

    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.name if user.role else None,
        "is_active": user.is_active,
    }


# ============================================================
# ASSIGN ROLE
# ============================================================

@router.patch(
    "/users/{user_id}/role",
    response_model=UserResponse
)
def change_user_role(
    user_id: int,
    request: RoleChangeRequest,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    )
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    new_role = (
        db.query(RoleModel)
        .filter(
            RoleModel.name == request.role.value
        )
        .first()
    )

    if new_role is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role"
        )

    old_role = (
        user.role.name
        if user.role
        else None
    )

    if old_role == new_role.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has this role"
        )

    user.role_id = new_role.id

    history = RoleChangeHistory(
        user_id=user.id,
        old_role=old_role,
        new_role=new_role.name,
        changed_by=current_user.id,
    )

    db.add(history)
    create_audit_log(
        db=db,
        event_type=ROLE_CHANGED,
        user_id=user.id,
        email=user.email,
        details=(
            f"Role changed from {old_role} "
            f"to {new_role.name} "
            f"by user {current_user.id}"
        ),
    )
    db.commit()
    db.refresh(user)

    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.name if user.role else None,
        "is_active": user.is_active,
    }

# ============================================================
# ROLE CHANGE HISTORY
# ============================================================

@router.get(
    "/users/{user_id}/role-history",
    response_model=list[RoleChangeHistoryResponse]
)
def role_change_history(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    )
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    history = (
        db.query(RoleChangeHistory)
        .filter(RoleChangeHistory.user_id == user_id)
        .order_by(
            RoleChangeHistory.changed_at.desc(),
            RoleChangeHistory.id.desc(),
    )
    .all()
)

    return [
        {
            "id": item.id,
            "user_id": item.user_id,
            "old_role": item.old_role,
            "new_role": item.new_role,
            "changed_by": item.changed_by,
            "changed_at": item.changed_at.isoformat(),
        }
        for item in history
    ]



# ============================================================
# FORCE RESET PASSWORD
# ============================================================

@router.post(
    "/users/{user_id}/force-reset-password"
)
def force_reset_password(
    user_id: int,
    request: ForceResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    )
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    '''validate_password(request.new_password)
    user.password = hash_password(
        request.new_password
    )'''
    validate_password(request.new_password)

    user.password = hash_password(
        request.new_password
    )

    now = datetime.now(timezone.utc)

    user.password_changed_at = now
    user.password_expires_at = (
        now + timedelta(days=90)
    )

# Revoke all active sessions after force password reset
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.is_revoked.is_(False),
    ).update(
    {
            RefreshToken.is_revoked: True
    },
    synchronize_session=False,
)
    
    db.commit()

    return {
        "message": "Password reset successfully"
}

# ============================================================
# ACTIVE SESSIONS
# ============================================================
@router.get(
    "/users/{user_id}/sessions",
    response_model=list[SessionResponse]
)
def list_user_sessions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    )
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    now = datetime.now(timezone.utc)

    sessions = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > now
        )
        .order_by(
            RefreshToken.created_at.desc()
        )
        .all()
    )

    return [
        {
            "id": session.id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "is_revoked": session.is_revoked,
        }
        for session in sessions
    ]

# ============================================================
# REVOKE SESSION
# ============================================================
@router.delete(
    "/users/{user_id}/sessions/{session_id}"
)
def revoke_user_session(
    user_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    )
):
    session = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.id == session_id,
            RefreshToken.user_id == user_id
        )
        .first()
    )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    if session.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already revoked"
        )

    session.is_revoked = True
    create_audit_log(
        db=db,
        event_type=TOKEN_REVOKED,
        user_id=user_id,
        details=(
            f"Session {session_id} revoked "
            f"by user {current_user.id}"
        ),
    )

    db.commit()

    return {
        "message": "Session revoked successfully"
    }


# ============================================================
# AUDIT LOGS
# ============================================================
@router.get(
    "/audit-logs",
    response_model=list[AuditLogResponse],
)
def get_audit_logs(
    user_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    ),
):
    query = db.query(AuthAuditLog)

    if user_id is not None:
        query = query.filter(
            AuthAuditLog.user_id == user_id
        )

    if event_type is not None:
        query = query.filter(
            AuthAuditLog.event_type == event_type
        )

    return (
        query
        .order_by(AuthAuditLog.created_at.desc())
        .limit(500)
        .all()
    )

# ============================================================
# SECURITY DASHBOARD
# ============================================================

@router.get(
    "/security-dashboard",
    response_model=SecurityDashboardResponse,
)
def security_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # --------------------------------------------------------
    # ADMIN ACCESS CHECK
    # --------------------------------------------------------
    if (
        not current_user.role
        or current_user.role.name not in {
            "ceo",
            "vp_operations",
        }
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    now = datetime.now(timezone.utc)

    last_24_hours = now - timedelta(hours=24)
    last_7_days = now - timedelta(days=7)

    # --------------------------------------------------------
    # 1. FAILED LOGIN TRENDS
    # --------------------------------------------------------
    failed_login_24h = (
        db.query(AuthAuditLog)
        .filter(
            AuthAuditLog.event_type == "LOGIN_FAILED",
            AuthAuditLog.created_at >= last_24_hours,
        )
        .count()
    )

    failed_login_7d = (
        db.query(AuthAuditLog)
        .filter(
            AuthAuditLog.event_type == "LOGIN_FAILED",
            AuthAuditLog.created_at >= last_7_days,
        )
        .count()
    )

    failed_login_trends = {
        "last_24_hours": failed_login_24h,
        "last_7_days": failed_login_7d,
    }

    # --------------------------------------------------------
    # 2. CURRENTLY ACTIVE SESSIONS
    # --------------------------------------------------------
    active_sessions = (
        db.query(
            RefreshToken,
            User.email,
        )
        .join(
            User,
            User.id == RefreshToken.user_id,
        )
        .filter(
            RefreshToken.is_revoked.is_(False),
            RefreshToken.expires_at > now,
            User.is_active.is_(True),
        )
        .order_by(
            RefreshToken.created_at.desc()
        )
        .all()
    )

    active_session_data = [
        {
            "session_id": session.id,
            "user_id": session.user_id,
            "email": email,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
        }
        for session, email in active_sessions
    ]

    # --------------------------------------------------------
    # 3. RECENT ROLE CHANGES
    # --------------------------------------------------------
    role_changes = (
        db.query(RoleChangeHistory)
        .order_by(
            RoleChangeHistory.changed_at.desc(),
            RoleChangeHistory.id.desc(),
        )
        .limit(20)
        .all()
    )

    role_change_data = [
        {
            "id": item.id,
            "user_id": item.user_id,
            "old_role": item.old_role,
            "new_role": item.new_role,
            "changed_by": item.changed_by,
            "changed_at": item.changed_at.isoformat(),
        }
        for item in role_changes
    ]

    # --------------------------------------------------------
    # 4. LOCKOUT EVENTS
    # --------------------------------------------------------
    lockout_events = (
        db.query(AuthAuditLog)
        .filter(
            AuthAuditLog.event_type == "ACCOUNT_LOCKED"
        )
        .order_by(
            AuthAuditLog.created_at.desc()
        )
        .limit(20)
        .all()
    )

    # --------------------------------------------------------
    # FINAL DASHBOARD RESPONSE
    # --------------------------------------------------------
    return {
        "failed_login_trends": failed_login_trends,

        "currently_active_sessions": len(
            active_session_data
        ),

        "active_sessions": active_session_data,

        "recent_role_changes": role_change_data,

        "lockout_events": lockout_events,
    }

# ============================================================
# ISSUE SERVICE API KEY
# ============================================================

@router.post(
    "/service-keys",
    response_model=ServiceAPIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_service_api_key(
    request: ServiceAPIKeyCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_any_role("ceo", "vp_operations")
    ),
):
    # Generate raw API key
    api_key = generate_service_api_key()

    # Hash before storing
    key_hash = hash_service_api_key(api_key)

    service_key = ServiceAPIKey(
    service_name=request.service_name,
    key_hash=key_hash,
    is_active=True,
    expires_at=request.expires_at,
    created_by=current_user.id,
   )
    db.add(service_key)
    db.commit()
    db.refresh(service_key)

    return {
        "id": service_key.id,
        "service_name": service_key.service_name,
        "api_key": api_key,
        "expires_at": service_key.expires_at,
        "is_active": service_key.is_active,
    }

# ============================================================
# LIST SERVICE API KEYS
# ============================================================

@router.get(
    "/service-keys",
    response_model=list[ServiceAPIKeyResponse],
)
def list_service_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_any_role("ceo", "vp_operations")
    ),
):
    service_keys = (
        db.query(ServiceAPIKey)
        .order_by(ServiceAPIKey.created_at.desc())
        .all()
    )

    return [
        {
            "id": key.id,
            "service_name": key.service_name,
            "expires_at": key.expires_at,
            "is_active": key.is_active,
            "created_at": key.created_at,
            "last_used_at": key.last_used_at,
        }
        for key in service_keys
    ]

# ============================================================
# REVOKE SERVICE API KEY
# ============================================================

@router.delete(
    "/service-keys/{key_id}"
)
def revoke_service_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_any_role("ceo", "vp_operations")
    ),
):
    service_key = (
        db.query(ServiceAPIKey)
        .filter(ServiceAPIKey.id == key_id)
        .first()
    )

    if service_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service API key not found",
        )

    if not service_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service API key already revoked",
        )

    service_key.is_active = False

    create_audit_log(
        db=db,
        event_type=TOKEN_REVOKED,
        user_id=current_user.id,
        details=(
            f"Service API key {key_id} "
            f"for {service_key.service_name} "
            f"revoked by admin {current_user.id}"
        ),
    )

    db.commit()

    return {
        "message": "Service API key revoked successfully",
        "key_id": key_id,
    }


#authroutes
from datetime import datetime, timedelta, timezone
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
    ROLE_HIERARCHY,
    oauth2_scheme,
    require_permission
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
# VERIFY
# ============================================================

@router.post("/service-verify")
def service_verify(
    service=Depends(verify_service_api_key),
):
    return {
        "authenticated": True,
        "service": service["service"],
        "auth_type": service["auth_type"],
    }

@router.post(
    "/verify",
    response_model=VerifyResponse,
)
def verify_access_token(
    current_user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
):
    cached_response = token_cache.get(token)

    if cached_response is not None:
        logger.info(
            "Token verification cache HIT | endpoint=/api/v1/auth/verify"
        )
        return cached_response

    response_data = {
        "valid": True,
        "user_id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role.name if current_user.role else None,
        "supplier_id": current_user.supplier_id,
        "is_active": current_user.is_active,
    }

    token_cache.set(token, response_data)

    logger.info(
        "Token verification cache MISS | user_id=%s | role=%s | endpoint=/api/v1/auth/verify",
        current_user.id,
        current_user.role.name if current_user.role else None,
    )

    return response_data


@router.get(
    "/inventory-test",
    dependencies=[
        Depends(require_permission("inventory:write"))
    ]
)
def inventory_test(user=Depends(get_current_user)):
    return {
        "message": "Inventory write permission granted",
        "user": {
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.name if user.role else None,
            "is_active": user.is_active,
        }
    }

