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
