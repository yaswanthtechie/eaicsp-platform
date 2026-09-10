from datetime import datetime, timedelta, timezone

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
import secrets
from app.models.password_reset_tokens import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.schemas.auth import RegisterRequest
from app.services.email_service import MockEmailService
from app.models.failed_login_attempts import FailedLoginAttempt
import threading
from collections import defaultdict
from app.services.audit_service import (
    LOGIN_SUCCESS,
    LOGIN_FAILED ,
    create_audit_log,
    PASSWORD_RESET
)

MAX_ATTEMPTS = 5
WINDOW = timedelta(minutes=15)

RESET_TOKEN_EXPIRE_MINUTES = 15
# ============================================================
# REFRESH TOKEN
# ============================================================

def save_refresh_token(
    db: Session,
    user_id: int,
    token: str,
    expires_at: datetime
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
    token: str
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

def revoke_refresh_token(
    db: Session,
    token: str
):
    refresh = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token == token
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
    email: str
):
    cutoff = (
        datetime.now(timezone.utc)
        - WINDOW
    )

    return (
        db.query(FailedLoginAttempt)
        .filter(
            FailedLoginAttempt.email == email,
            FailedLoginAttempt.attempted_at >= cutoff,
        )
        .count()
    )


def get_recent_attempts_by_ip(
    db: Session,
    ip_address: str
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


def check_login_rate_limit(
    db: Session,
    email: str,
    client_ip: str
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

# module-level, one lock per (email, ip) bucket
_rate_limit_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
_rate_limit_locks_guard = threading.Lock()

def _get_bucket_lock(email: str, client_ip: str) -> threading.Lock:
    key = f"{email}:{client_ip}"
    with _rate_limit_locks_guard:
        return _rate_limit_locks[key]

# ============================================================
# REGISTER
# ============================================================

def register_user(
    db: Session,
    request: RegisterRequest
):
    existing = (
        db.query(User)
        .filter(
            User.email == request.email
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )

    #Validate password before hashing
    validate_password(request.password)
    
    hashed_password = hash_password(
        request.password
    )

    user = User(
        email=request.email,
        full_name=request.full_name,
        password=hashed_password,
        is_active=True,
        role_id=None

    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "message": "User registered successfully"
    }

# ============================================================
# LOGIN
# ============================================================

def login(
    db: Session,
    username: str,
    password: str
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
        user.password
    ):
        return None

    return user

def login_user(
    db: Session,
    username: str,
    password: str,
    client_ip: str
):
    username = username.lower()

    lock = _get_bucket_lock(username, client_ip)

    with lock:
        check_login_rate_limit(
            db=db,
            email=username,
            client_ip=client_ip,
        )

        user = login(
            db=db,
            username=username,
            password=password,
        )

        if not user:
            log_failed_login(
                db=db,
                email=username,
                ip_address=client_ip,
            )

            create_audit_log(
                db=db,
                event_type=LOGIN_FAILED,
                email=username,
                ip_address=client_ip,
                details="Invalid credentials",
            )

            db.commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
   
    # --------------------------------------------------------
    # Wrong username OR wrong password
    # --------------------------------------------------------

    if not user:
        log_failed_login(
            db=db,
            email=username,
            ip_address=client_ip,
        )
        create_audit_log(
            db=db,
            event_type=LOGIN_FAILED,
            email=username,
            ip_address=client_ip,
            details="Invalid credentials",
        )
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        log_failed_login(
            db=db,
            email=username,
            ip_address=client_ip,
        )
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

    if not user.role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User role is not assigned",
        )
   
    # --------------------------------------------------------
    # Access token
    # --------------------------------------------------------

    access_token = create_access_token(
        {
            "sub": user.email,
            "role": user.role.name,
            "user_id": user.id,
        }
    )

    # --------------------------------------------------------
    # Refresh token
    # --------------------------------------------------------

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
    create_audit_log(
        db=db,
        event_type=LOGIN_SUCCESS,
        user_id=user.id,
        email=user.email,
        ip_address=client_ip,
        details="Login Successful"
    )
    db.commit()

    
    # --------------------------------------------------------
    # Clear previous failed login attempts
    # --------------------------------------------------------

    db.query(FailedLoginAttempt).filter(
        FailedLoginAttempt.email == username,
        FailedLoginAttempt.ip_address == client_ip,
    ).delete(
        synchronize_session=False,
    )

    db.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


def request_password_reset(
    db: Session,
    email: str,
):
    email = email.lower()

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )
    if user is None:
        return

    
    # --------------------------------------------------------
    # Invalidate all previous unused reset tokens.
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
    now = datetime.utcnow()

    if reset_token.expires_at <= now:
        raise HTTPException(
        status_code=400,
        detail="Password reset token has expired",
    )

    user = (
        db.query(User)
        .filter(User.id == reset_token.user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password reset token",
        )

    validate_password(new_password)

    user.password = hash_password(new_password)

    db.query(RefreshToken).filter(
    RefreshToken.user_id == user.id,
    RefreshToken.is_revoked.is_(False),
    ).update(
    {
        RefreshToken.is_revoked: True
    },
    synchronize_session=False,
    )

    reset_token.used = True
    create_audit_log(
        db=db,
        event_type=PASSWORD_RESET,
        user_id=user.id,
        email=user.email,
        details="Password reset completed",
    )
    db.commit()
