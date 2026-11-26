import logging
import secrets
import threading
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import jwt
from fastapi import HTTPException, status
from jwt.exceptions import InvalidTokenError
from sqlalchemy import CursorResult, update
from sqlalchemy.orm import Session

from app.core import config as app_config
from app.core.event_publisher import publish_event
from app.core.password_validator import validate_password
from app.core.revocation_store import (
    is_family_revoked_in_cache,
    revoke_family_cache,
    set_family_active_token,
)
from app.core.security import (
    build_access_claims,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.core.token_cache import token_cache
from app.database import get_db_now
from app.models.failed_login_attempts import FailedLoginAttempt
from app.models.password_reset_tokens import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.users import User
from app.schemas.auth import RegisterRequest
from app.services.audit_service import (
    ACCOUNT_LOCKED,
    LOGIN_FAILED,
    LOGIN_SUCCESS,
    MFA_FAILED,
    MFA_VERIFIED,
    PASSWORD_RESET,
    TOKEN_REVOKED,
    create_audit_log,
)
from app.services.email_service import MockEmailService
from app.services.mfa_service import create_mfa_challenge, verify_mfa_challenge

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
# Generated once per process to avoid skipping password verification
# when the supplied username does not match an account.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))

# ============================================================
# REFRESH TOKEN
# ============================================================


def save_refresh_token(
    db: Session,
    user_id: int,
    token: str,
    expires_at: datetime,
    family_id: str | None = None,
):
    token_hash = hash_token(token)

    if family_id is None:
        try:
            payload = decode_token(token)
            family_id = payload.get("family_id")
        except InvalidTokenError:
            pass
    if family_id is None:
        family_id = str(uuid.uuid4())

    refresh = RefreshToken(
        user_id=user_id,
        token=token_hash,
        expires_at=expires_at,
        family_id=family_id,
    )

    db.add(refresh)

    return refresh


def get_refresh_token(
    db: Session,
    token: str,
):
    now = get_db_now(db)
    token_hash = hash_token(token)

    refresh = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token == token_hash,
            RefreshToken.is_revoked.is_(False),
            RefreshToken.expires_at > now,
        )
        .first()
    )

    if refresh is None:
        return None

    user = db.query(User).filter(User.id == refresh.user_id).first()

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
    token_hash = hash_token(token)
    refresh = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token == token_hash,
        )
        .first()
    )

    if refresh is None:
        return False
    refresh.is_revoked = True
    refresh.revoked_at = datetime.now(UTC)
    return True


def revoke_token_family(
    db: Session,
    family_id: str,
) -> None:
    if not family_id:
        return
    now = get_db_now(db)
    db.query(RefreshToken).filter(
        RefreshToken.family_id == family_id,
        RefreshToken.is_revoked.is_(False),
    ).update(
        {RefreshToken.is_revoked: True, RefreshToken.revoked_at: now},
        synchronize_session=False,
    )
    db.commit()
    revoke_family_cache(
        family_id,
        ttl_seconds=app_config.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )


def logout_family(
    db: Session,
    refresh: RefreshToken | None = None,
    *,
    family_id: str | None = None,
    user_id: int | None = None,
) -> None:
    """Revoke all refresh tokens in the family and cache family revocation after DB commit."""
    now = get_db_now(db)
    fam_id = refresh.family_id if refresh is not None else family_id
    uid = refresh.user_id if refresh is not None else user_id

    if fam_id:
        db.query(RefreshToken).filter(
            RefreshToken.family_id == fam_id,
            RefreshToken.is_revoked.is_(False),
        ).update(
            {RefreshToken.is_revoked: True, RefreshToken.revoked_at: now},
            synchronize_session=False,
        )
    elif refresh is not None:
        refresh.is_revoked = True
        refresh.revoked_at = now

    if uid is not None:
        create_audit_log(
            db=db,
            event_type=TOKEN_REVOKED,
            user_id=uid,
            details="Refresh token family and access token revoked during logout",
        )

    db.commit()

    if fam_id:
        revoke_family_cache(
            fam_id,
            ttl_seconds=app_config.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        )


def rotate_refresh_token(db: Session, raw_token: str) -> dict[str, str]:
    """Rotate a refresh token atomically under the same family.

    Enforces:
    - Single-winner atomic database UPDATE.
    - Configurable grace period window (default: 10s) for in-flight concurrent requests.
    - Token family reuse detection when an ancestor is replayed with active descendants.
    - Fast-path Redis caching and cache reconstruction from DB.
    - Redis cache writes occur strictly AFTER PostgreSQL commits.
    """
    try:
        payload = decode_token(raw_token)
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from None

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    token_hash = hash_token(raw_token)
    request_db_time = get_db_now(db)

    # Fast-path Redis cache check for family revocation
    family_id_claim = payload.get("family_id")
    if family_id_claim and is_family_revoked_in_cache(family_id_claim):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )

    # Atomic PostgreSQL UPDATE to check and mark the refresh token as used
    stmt = (
        update(RefreshToken)
        .where(
            RefreshToken.token == token_hash,
            RefreshToken.is_revoked.is_(False),
            RefreshToken.expires_at > request_db_time,
        )
        .values(
            is_revoked=True,
            revoked_at=request_db_time,
        )
    )
    result = cast(CursorResult[Any], db.execute(stmt))

    if result.rowcount == 0:
        # Atomic update failed: token not found, expired, or already used/revoked
        existing = (
            db.query(RefreshToken).filter(RefreshToken.token == token_hash).first()
        )

        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked refresh token",
            )

        expires_at = existing.expires_at
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= request_db_time:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired refresh token",
                )

        # Token was already revoked / used.
        # Check whether this request arrived within the configurable grace period.
        revoked_at = existing.revoked_at
        if revoked_at is not None:
            if revoked_at.tzinfo is None:
                revoked_at = revoked_at.replace(tzinfo=UTC)
            elapsed_at_arrival = (request_db_time - revoked_at).total_seconds()
        else:
            elapsed_at_arrival = 999999.0

        if (
            -app_config.REFRESH_TOKEN_GRACE_PERIOD_SECONDS
            <= elapsed_at_arrival
            <= app_config.REFRESH_TOKEN_GRACE_PERIOD_SECONDS
        ):
            # Concurrent in-flight request or loser within grace period: return 401 without family revocation.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked refresh token",
            )

        # Token arrived after grace period (> 10s).
        # Check for genuine reuse:
        # Only treat as genuine reuse if the family actually has active descendants to revoke!
        # If the family was already legitimately revoked (e.g. via logout, password reset,
        # admin session revocation, or previous reuse revocation), there are no active tokens
        # to revoke, and classifying it as a new reuse event would trigger a false security alert.
        fam_id = existing.family_id
        if fam_id:
            active_descendants = (
                db.query(RefreshToken)
                .filter(
                    RefreshToken.family_id == fam_id,
                    RefreshToken.is_revoked.is_(False),
                )
                .update(
                    {
                        RefreshToken.is_revoked: True,
                        RefreshToken.revoked_at: request_db_time,
                    },
                    synchronize_session=False,
                )
            )
            if active_descendants > 0:
                # Active tokens were compromised/revoked by this reuse attempt
                token_cache.invalidate_user(existing.user_id)
                logger.warning(
                    "Refresh token reuse detected: user_id=%s, family_id=%s. Entire token family revoked.",
                    existing.user_id,
                    fam_id,
                )
                create_audit_log(
                    db=db,
                    event_type=TOKEN_REVOKED,
                    user_id=existing.user_id,
                    details=f"Token reuse detected for family_id={fam_id}. Entire token family revoked.",
                )
                db.commit()
                # Redis family-revocation cache write strictly AFTER PostgreSQL commit
                revoke_family_cache(
                    fam_id,
                    ttl_seconds=app_config.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
                )
            else:
                db.rollback()
        else:
            db.rollback()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )

    # Atomic update succeeded: 1 row transitioned from active to revoked
    refresh = db.query(RefreshToken).filter(RefreshToken.token == token_hash).first()
    if refresh is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )

    user = db.query(User).filter(User.id == refresh.user_id).first()

    if user is None or not user.is_active:
        if refresh.family_id:
            revoke_token_family(db, refresh.family_id)
        else:
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user"
        )

    if user.role is None:
        if refresh.family_id:
            revoke_token_family(db, refresh.family_id)
        else:
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user"
        )

    family_id = refresh.family_id or family_id_claim or str(uuid.uuid4())

    new_access_token = create_access_token(build_access_claims(user))
    new_refresh_token = create_refresh_token(
        {
            "sub": user.email,
            "user_id": user.id,
        },
        family_id=family_id,
    )

    new_refresh_expires_at = request_db_time + timedelta(
        days=app_config.REFRESH_TOKEN_EXPIRE_DAYS
    )

    # Save new refresh token under the same family
    save_refresh_token(
        db=db,
        user_id=user.id,
        token=new_refresh_token,
        expires_at=new_refresh_expires_at,
        family_id=family_id,
    )

    db.commit()

    # Update active token hash in Redis cache (best-effort, after DB commit)
    new_token_hash = hash_token(new_refresh_token)
    set_family_active_token(
        family_id,
        new_token_hash,
        ttl_seconds=app_config.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


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
        attempted_at=datetime.now(UTC),
    )

    db.add(failed_attempt)
    db.commit()


def get_recent_attempts_by_email(
    db: Session,
    email: str,
):
    cutoff = datetime.now(UTC) - WINDOW

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
    cutoff = datetime.now(UTC) - WINDOW

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

    if email_attempts >= MAX_ATTEMPTS or ip_attempts >= MAX_ATTEMPTS:
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

    now = datetime.now(UTC)

    locked_until = user.locked_until

    # SQLite can return timezone-naive datetime values.
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=UTC)

    if locked_until > now:
        return True
    # Lock period expired
    user.locked_until = None

    return False


# ============================================================
# RATE LIMIT LOCKS
# ============================================================
# One lock per email + IP bucket
_rate_limit_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)

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

    existing = db.query(User).filter(User.email == email_address).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists",
        )

    # Validate password before hashing
    validate_password(request.password)

    hashed_password = hash_password(request.password)
    now = get_db_now(db)
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
    return {"message": "User registered successfully"}


# ============================================================
# BASIC LOGIN
# ============================================================


def login(
    db: Session,
    username: str,
    password: str,
):
    username = username.lower()

    user = db.query(User).filter(User.email == username).first()

    password_hash = user.password if user is not None else DUMMY_PASSWORD_HASH

    if not verify_password(password, password_hash):
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

        user = db.query(User).filter(User.email == username).first()

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

        password_hash = user.password if user is not None else DUMMY_PASSWORD_HASH
        password_is_valid = verify_password(password, password_hash)

        if user is None or not password_is_valid:
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
                user.locked_until = datetime.now(UTC) + LOCKOUT_DURATION

                # Keep existing Redis cache invalidation
                token_cache.invalidate_user(user.id)

                # Keep existing audit behavior
                create_audit_log(
                    db=db,
                    event_type=ACCOUNT_LOCKED,
                    user_id=user.id,
                    email=user.email,
                    ip_address=client_ip,
                    details=(
                        f"Account locked after {MAX_ATTEMPTS} failed login attempts"
                    ),
                )

                # ------------------------------------------------
                # Commit lock + audit first
                # ------------------------------------------------

                db.commit()

                # ------------------------------------------------
                # Publish shared Kafka event
                # ------------------------------------------------
                # The lock and audit record are already committed.
                # publish_event never raises and gives up after
                # KAFKA_PUBLISH_TIMEOUT_SECONDS, so a Kafka outage can
                # neither undo the lock nor stall this request.
                publish_event(
                    "platform.user.locked",
                    {
                        "user_id": user.id,
                    },
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

        now = get_db_now(db)

        if user.password_expires_at:
            password_expires_at = user.password_expires_at

            if password_expires_at.tzinfo is None:
                password_expires_at = password_expires_at.replace(tzinfo=UTC)

            if password_expires_at <= now:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=("Password has expired. Please reset your password."),
                )

        # ----------------------------------------------------
        # 10-11. MFA challenge (if enabled) OR tokens
        # ----------------------------------------------------

        if app_config.MFA_ENABLED:
            challenge_id, otp = create_mfa_challenge(user_id=user.id)

            MockEmailService.send_mfa_otp(
                email=user.email,
                otp=otp,
            )

            login_response = {
                "mfa_required": True,
                "challenge_id": challenge_id,
                "message": "OTP sent. Verify the OTP to complete login.",
            }

            audit_details = "Password authentication successful; MFA required"

        else:
            access_token = create_access_token(build_access_claims(user))

            refresh_token = create_refresh_token(
                {
                    "sub": user.email,
                    "user_id": user.id,
                }
            )

            save_refresh_token(
                db=db,
                user_id=user.id,
                token=refresh_token,
                expires_at=(
                    datetime.now(UTC)
                    + timedelta(days=app_config.REFRESH_TOKEN_EXPIRE_DAYS)
                ),
            )

            login_response = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
            }

            audit_details = "Login Successful"

        # ----------------------------------------------------
        # 12. Successful password authentication audit
        # ----------------------------------------------------

        create_audit_log(
            db=db,
            event_type=LOGIN_SUCCESS,
            user_id=user.id,
            email=user.email,
            ip_address=client_ip,
            details=audit_details,
        )

        logger.info(
            "Password authentication succeeded | user_id=%s | role=%s | %s",
            user.id,
            user.role.name,
            audit_details,
        )

        # ----------------------------------------------------
        # 13. Clear failed attempts
        # ----------------------------------------------------

        db.query(FailedLoginAttempt).filter(
            FailedLoginAttempt.email == username,
        ).delete(
            synchronize_session=False,
        )

        db.commit()

        # ----------------------------------------------------
        # 14. Return MFA challenge / tokens
        # ----------------------------------------------------
        return login_response


# ============================================================
# PASSWORD RESET REQUEST
# ============================================================


def request_password_reset(
    db: Session,
    email: str,
):
    email = email.lower()

    user = db.query(User).filter(User.email == email).first()

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

    expires_at = datetime.now(UTC) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)

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
        db.query(PasswordResetToken).filter(PasswordResetToken.token == token).first()
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

    now = get_db_now(db)

    expires_at = reset_token.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token has expired",
        )

    user = db.query(User).filter(User.id == reset_token.user_id).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password reset token",
        )

    # Validate new password
    validate_password(new_password)

    # Update password
    user.password = hash_password(new_password)

    token_cache.invalidate_user(user.id)

    # Update password lifecycle dates
    user.password_changed_at = now
    user.password_expires_at = now + timedelta(days=90)

    # Unlock account after successful password reset
    user.locked_until = None

    # Collect active family IDs to evict from Redis cache after DB commit
    active_family_ids = [
        row[0]
        for row in db.query(RefreshToken.family_id)
        .filter(
            RefreshToken.user_id == user.id,
            RefreshToken.is_revoked.is_(False),
            RefreshToken.family_id.isnot(None),
        )
        .distinct()
        .all()
        if row[0] is not None
    ]

    # Revoke all active refresh tokens with revoked_at set
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.is_revoked.is_(False),
    ).update(
        {RefreshToken.is_revoked: True, RefreshToken.revoked_at: now},
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

    # Evict Redis family cache after successful DB commit
    for fid in active_family_ids:
        if fid:
            revoke_family_cache(fid)


def complete_mfa_login(
    db: Session, challenge_id: str, otp: str, client_ip: str
) -> dict:
    """Verify the OTP for a pending MFA challenge and issue tokens."""

    user_id = verify_mfa_challenge(challenge_id, otp)

    user = (
        db.query(User).filter(User.id == user_id).first()
        if user_id is not None
        else None
    )

    if user is None or not user.is_active or user.role is None:
        create_audit_log(
            db=db,
            event_type=MFA_FAILED,
            user_id=user.id if user else None,
            email=user.email if user else None,
            ip_address=client_ip,
            details="MFA verification failed (invalid, expired, reused or wrong OTP)",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MFA code",
        )

    access_token = create_access_token(build_access_claims(user))
    refresh_token = create_refresh_token({"sub": user.email, "user_id": user.id})

    save_refresh_token(
        db=db,
        user_id=user.id,
        token=refresh_token,
        expires_at=datetime.now(UTC)
        + timedelta(days=app_config.REFRESH_TOKEN_EXPIRE_DAYS),
    )

    create_audit_log(
        db=db,
        event_type=MFA_VERIFIED,
        user_id=user.id,
        email=user.email,
        ip_address=client_ip,
        details="MFA verification successful; tokens issued",
    )
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
