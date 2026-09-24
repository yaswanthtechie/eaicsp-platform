from collections import defaultdict
from datetime import datetime, timedelta, timezone
import threading
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.abuse_event import AbuseEvent
from app.services.audit_service import create_audit_log

# =========================================================
# Abuse Event Types
# =========================================================

RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
LOGIN_BRUTE_FORCE = "LOGIN_BRUTE_FORCE"
MFA_ABUSE = "MFA_ABUSE"
SSO_ABUSE = "SSO_ABUSE"

# =========================================================
# Rate-Limit Configuration
# endpoint -> (maximum requests, window in seconds)
# =========================================================

RATE_LIMITS = {
    # General login request protection
    "/api/v1/auth/login": (20, 60),

    # MFA brute-force protection
    "/api/v1/auth/mfa/verify": (5, 300),

    # Token verification protection
    "/api/v1/auth/verify": (100, 60),

    # SSO abuse protection
    "/api/v1/auth/sso/login": (20, 60),
}

# =========================================================
# In-Memory Request Buckets
# =========================================================
# Rate limiting is maintained per:
#     caller_service + endpoint
#
# Examples:
#     inventory:/api/v1/auth/verify
#     supplier:/api/v1/auth/verify
#     compliance:/api/v1/auth/verify
#
# =========================================================

_request_buckets = defaultdict(list)

_bucket_lock = threading.Lock()

# =========================================================
# Rate-Limit Checker
# =========================================================

def check_rate_limit(
    db: Session,
    ip_address: str,
    endpoint: str,
    abuse_event_type: str = RATE_LIMIT_EXCEEDED,
    caller_service: str = "unknown",
):
    """
    Check whether a caller service has exceeded the configured
    request limit for an endpoint.

    Rate limiting is performed per:

        caller_service + endpoint

    When the limit is exceeded:

        1. Create an audit/security log.
        2. Create an AbuseEvent.
        3. Reject the request with HTTP 429.
    """
    # -----------------------------------------------------
    # Get endpoint-specific configuration
    # -----------------------------------------------------

    max_requests, window_seconds = RATE_LIMITS.get(
        endpoint,
        (100, 60),
    )
    now = datetime.now(timezone.utc)
    # -----------------------------------------------------
    # Normalize caller service
    # -----------------------------------------------------

    caller_service = (
        caller_service.strip().lower()
        if caller_service and caller_service.strip()
        else "unknown"
    )

    # -----------------------------------------------------
    # Create caller-specific bucket
    # -----------------------------------------------------

    key = f"{caller_service}:{endpoint}"

    with _bucket_lock:

        timestamps = _request_buckets[key]

        # -------------------------------------------------
        # Remove expired requests
        # -------------------------------------------------

        cutoff = now - timedelta(
            seconds=window_seconds
        )

        timestamps[:] = [
            timestamp
            for timestamp in timestamps
            if timestamp > cutoff
        ]

        # -------------------------------------------------
        # Rate limit exceeded
        # -------------------------------------------------

        if len(timestamps) >= max_requests:

            details = (
                f"{abuse_event_type}: "
                f"Rate limit exceeded: "
                f"{max_requests} requests/"
                f"{window_seconds} seconds; "
                f"caller_service={caller_service}"
            )

            # -------------------------------------------------
            # 1. Audit / compliance log
            # -------------------------------------------------

            create_audit_log(
                db=db,
                event_type=RATE_LIMIT_EXCEEDED,
                ip_address=ip_address,
                details=details,
            )

            # -------------------------------------------------
            # 2. Abuse event
            # -------------------------------------------------

            event = AbuseEvent(
                ip_address=ip_address,
                endpoint=endpoint,
                event_type=abuse_event_type,
                request_count=len(timestamps),
                detected_at=now,
                details=details,
            )

            db.add(event)

            # Save audit + abuse event
            db.commit()

            # -------------------------------------------------
            # 3. Reject request
            # -------------------------------------------------

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={
                    "Retry-After": str(window_seconds),
                },
            )

        # -------------------------------------------------
        # Request is within allowed limit
        # -------------------------------------------------

        timestamps.append(now)