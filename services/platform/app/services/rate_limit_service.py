from collections import defaultdict
from datetime import datetime, timedelta, timezone
import threading
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.abuse_event import AbuseEvent
from app.services.audit_service import create_audit_log
from app.core.config import KNOWN_CALLER_SERVICES

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
_MAX_WINDOW_SECONDS = max(window for _, window in RATE_LIMITS.values())
_last_abuse_event_at = {}
_bucket_lock = threading.Lock()

# =========================================================
# Rate-Limit Checker
# =========================================================

def check_rate_limit(
    db: Session,
    ip_address: str,
    endpoint: str,
    abuse_event_type: str = RATE_LIMIT_EXCEEDED,
    caller_service: str | None = None,
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

    # The header is supplied by the client, so it is only trusted to pick
    # a bucket when it names a known service. Anything else shares the
    # "unknown" bucket for this IP; otherwise a new header value on every
    # request would get a fresh bucket and bypass the limit.
    if caller_service not in KNOWN_CALLER_SERVICES:
        caller_service = "unknown"

    # -----------------------------------------------------
    # Create caller-specific bucket
    # -----------------------------------------------------

    key = f"{caller_service}:{ip_address}:{endpoint}"

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
        # Drop idle buckets so memory does not grow with every IP seen.
        # Use the LONGEST configured window: a /login request must never
        # delete a /mfa/verify bucket that is still inside its 300s window.
        idle_cutoff = now - timedelta(seconds=_MAX_WINDOW_SECONDS)
        for stale_key in [
            k for k, v in _request_buckets.items()
            if k != key and (not v or v[-1] <= idle_cutoff)
        ]:
            del _request_buckets[stale_key]
            _last_abuse_event_at.pop(stale_key, None)

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
            # 1 + 2. Audit log and abuse event, at most once per
            # window per bucket. Writing a row for every rejected
            # request would turn a flood into a flood of DB writes.
            # -------------------------------------------------

            last_recorded = _last_abuse_event_at.get(key)

            should_record_abuse_event = (
                last_recorded is None
                or (now - last_recorded).total_seconds() >= window_seconds
            )

            if should_record_abuse_event:
                create_audit_log(
                    db=db,
                    event_type=RATE_LIMIT_EXCEEDED,
                    ip_address=ip_address,
                    details=details,
                )

                event = AbuseEvent(
                    ip_address=ip_address,
                    endpoint=endpoint,
                    event_type=abuse_event_type,
                    request_count=len(timestamps),
                    detected_at=now,
                    details=details,
                )

                db.add(event)
                _last_abuse_event_at[key] = now
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

