from datetime import datetime, timezone
import uuid
import redis
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.abuse_event import AbuseEvent
from app.services.audit_service import create_audit_log
from app.core.config import KNOWN_CALLER_SERVICES
from app.core.redis_client import get_redis

# ============================================================
# Abuse Event Types
# ============================================================

RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
LOGIN_BRUTE_FORCE = "LOGIN_BRUTE_FORCE"
MFA_ABUSE = "MFA_ABUSE"
SSO_ABUSE = "SSO_ABUSE"


# ============================================================
# Rate-Limit Configuration
# endpoint -> (maximum requests, window in seconds)
# ============================================================

RATE_LIMITS = {
    "/api/v1/auth/login": (20, 60),
    "/api/v1/auth/mfa/verify": (5, 300),
    "/api/v1/auth/verify": (100, 60),
    "/api/v1/auth/sso/login": (20, 60),
}


# ============================================================
# Redis Key Prefix
# ============================================================

RATE_LIMIT_PREFIX = "platform:rate_limit:"


# ============================================================
# Backward Compatibility
# ============================================================
#
# Existing tests/imports expect these module-level names.
#
# IMPORTANT:
# These are NOT used for rate-limit state anymore.
# Redis is the shared source of truth.
# ============================================================

_request_buckets = {}
_last_abuse_event_at = {}


# ============================================================
# Atomic Redis Sliding-Window Script
# ============================================================

RATE_LIMIT_SCRIPT = """
local key = KEYS[1]

local now = tonumber(ARGV[1])
local cutoff = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local expire_seconds = tonumber(ARGV[4])
local member = ARGV[5]

-- Remove requests outside the sliding window.
redis.call("ZREMRANGEBYSCORE", key, "-inf", cutoff)

-- Count requests currently inside the window.
local current_count = redis.call("ZCARD", key)

-- Reject when the limit has already been reached.
if current_count >= max_requests then
    return 0
end

-- Add current request.
redis.call("ZADD", key, now, member)

-- Prevent abandoned keys from remaining forever.
redis.call("EXPIRE", key, expire_seconds)

return 1
"""


# ============================================================
# Build Redis Rate-Limit Key
# ============================================================

def _make_key(
    caller_service: str,
    ip_address: str,
    endpoint: str,
) -> str:
    """
    Build the shared Redis rate-limit key.

    Rate limiting is isolated by:

        caller_service + IP address + endpoint
    """

    return (
        f"{RATE_LIMIT_PREFIX}"
        f"{caller_service}:"
        f"{ip_address}:"
        f"{endpoint}"
    )


# ============================================================
# Rate-Limit Checker
# ============================================================

def check_rate_limit(
    db: Session,
    ip_address: str,
    endpoint: str,
    abuse_event_type: str = RATE_LIMIT_EXCEEDED,
    caller_service: str | None = None,
):
    """
    Redis-backed sliding-window rate limiter.

    Shared state is stored in Redis so multiple Platform
    Service instances use the same rate-limit counters.

    Rate limiting is performed per:

        caller_service + IP address + endpoint

    When the limit is exceeded:

        1. Security audit event is recorded once per window.
        2. AbuseEvent is recorded once per window.
        3. HTTP 429 is returned.

    If Redis is unavailable:

        HTTP 503 is returned.

    The limiter fails closed because bypassing the shared
    security state would allow the rate limit to be bypassed.
    """

    # --------------------------------------------------------
    # Endpoint configuration
    # --------------------------------------------------------

    max_requests, window_seconds = RATE_LIMITS.get(
        endpoint,
        (100, 60),
    )

    # --------------------------------------------------------
    # Normalize caller service
    # --------------------------------------------------------

    caller_service = (
        caller_service.strip().lower()
        if caller_service and caller_service.strip()
        else "unknown"
    )

    # Only known services receive their own bucket.
    # Unknown values share the "unknown" bucket.
    if caller_service not in KNOWN_CALLER_SERVICES:
        caller_service = "unknown"

    # --------------------------------------------------------
    # Redis key
    # --------------------------------------------------------

    key = _make_key(
        caller_service=caller_service,
        ip_address=ip_address,
        endpoint=endpoint,
    )

    # --------------------------------------------------------
    # Current time
    # --------------------------------------------------------

    now = datetime.now(timezone.utc)
    now_timestamp = now.timestamp()
    cutoff = now_timestamp - window_seconds

    # Unique member for the Redis sorted set.
    member = f"{now_timestamp}:{uuid.uuid4().hex}"

    redis_client = get_redis()

    try:
        # ----------------------------------------------------
        # Atomic rate-limit operation
        # ----------------------------------------------------

        result = redis_client.eval(
            RATE_LIMIT_SCRIPT,
            1,
            key,
            now_timestamp,
            cutoff,
            max_requests,
            window_seconds + 5,
            member,
        )

        allowed = int(result) == 1

        if allowed:
            return

        # ----------------------------------------------------
        # Rate limit exceeded
        # ----------------------------------------------------

        details = (
            f"{abuse_event_type}: "
            f"Rate limit exceeded: "
            f"{max_requests} requests/"
            f"{window_seconds} seconds; "
            f"caller_service={caller_service}"
        )

        # ----------------------------------------------------
        # Shared abuse-event marker
        # ----------------------------------------------------
        #
        # SET NX makes recording happen once across ALL
        # Platform Service instances.
        # ----------------------------------------------------

        abuse_marker_key = f"{key}:abuse-recorded"

        should_record = redis_client.set(
            abuse_marker_key,
            "1",
            nx=True,
            ex=window_seconds,
        )

        if should_record:
            try:
                # --------------------------------------------
                # Audit log
                # --------------------------------------------

                create_audit_log(
                    db=db,
                    event_type=RATE_LIMIT_EXCEEDED,
                    ip_address=ip_address,
                    details=details,
                )

                # --------------------------------------------
                # Abuse event
                # --------------------------------------------

                current_count = redis_client.zcard(key)

                event = AbuseEvent(
                    ip_address=ip_address,
                    endpoint=endpoint,
                    event_type=abuse_event_type,
                    request_count=current_count,
                    detected_at=now,
                    details=details,
                )

                db.add(event)
                db.commit()

            except Exception:
                db.rollback()

                # Allow another request to retry recording
                # the security event.
                try:
                    redis_client.delete(abuse_marker_key)
                except redis.RedisError:
                    pass

                raise

        # ----------------------------------------------------
        # Reject request
        # ----------------------------------------------------

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
            headers={
                "Retry-After": str(window_seconds),
            },
        )

    except HTTPException:
        # Preserve intentional 429.
        raise

    except redis.RedisError:
        # Redis is required for the shared rate limiter.
        # Never silently bypass the security control.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiting service unavailable",
        )