"""
Per-user and per-role rate limiting middleware for the API Gateway.
"""

import base64
import json
import logging
import threading
import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.middleware.ratelimit import get_real_ip

try:
    import jwt
except ImportError:
    jwt = None  # type: ignore

logger = logging.getLogger("api_gateway.rate_limit")


# ---------------------------------------------------------------------------
# In-Memory Rate Limiter
# ---------------------------------------------------------------------------

class InMemoryRateLimiter:
    """
    Thread-safe in-memory rate limiter using fixed window strategy.
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Maps identity_key -> [count, window_start_timestamp]
        self._buckets: dict[str, list] = {}

    def check_and_update(
        self,
        key: str,
        limit: int,
        window_seconds: float,
    ) -> tuple[bool, int, int, int]:
        """
        Check rate limit for `key`.

        Returns:
            (allowed: bool, limit: int, remaining: int, retry_after: int)
        """
        now = time.time()
        with self._lock:
            if key in self._buckets:
                count, window_start = self._buckets[key]
                elapsed = now - window_start
                if elapsed >= window_seconds:
                    count = 1
                    window_start = now
                    self._buckets[key] = [count, window_start]
                else:
                    count += 1
                    self._buckets[key] = [count, window_start]
            else:
                count = 1
                window_start = now
                self._buckets[key] = [count, window_start]

            elapsed = now - window_start
            remaining = max(0, limit - count)
            retry_after = max(1, int(window_seconds - elapsed))

            if count > limit:
                return False, limit, 0, retry_after

            return True, limit, remaining, retry_after

    def reset(self):
        """Reset all rate limit buckets."""
        with self._lock:
            self._buckets.clear()


# Global singleton rate limiter instance
in_memory_limiter = InMemoryRateLimiter()


# ---------------------------------------------------------------------------
# JWT Identity Helper
# ---------------------------------------------------------------------------

def extract_jwt_identity(
    request: Request,
) -> tuple[str | None, str | None]:
    """
    Extract user_id and role from Authorization: Bearer <JWT> header.

    Returns:
        (user_id, role)
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return None, None

    token = auth_header[7:].strip()
    if not token:
        return None, None

    payload = None

    if jwt is not None:
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except (jwt.PyJWTError, ValueError, TypeError, AttributeError) as exc:
            logger.debug("Failed to decode JWT via PyJWT: %s", exc)
            return None, None
    else:
        # Fallback to base64url payload decoding ONLY if PyJWT package is not installed
        try:
            parts = token.split(".")
            if len(parts) >= 2:
                payload_b64 = parts[1]
                payload_b64 += "=" * (-len(payload_b64) % 4)
                payload_bytes = base64.urlsafe_b64decode(payload_b64)
                payload = json.loads(payload_bytes)
        except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as exc:
            logger.debug("Failed to base64 decode JWT token: %s", exc)
            return None, None

    if not isinstance(payload, dict):
        return None, None

    user_id = payload.get("user_id") or payload.get("sub")
    role = payload.get("role") or payload.get("roles")

    if isinstance(role, list) and len(role) > 0:
        role = role[0]

    user_id_str = str(user_id) if user_id is not None else None
    role_str = str(role) if role is not None else None

    return user_id_str, role_str


# ---------------------------------------------------------------------------
# Per-User / Per-Role Rate Limiting Middleware
# ---------------------------------------------------------------------------

class PerUserRoleRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to rate limit requests per authenticated user, per role,
    or fallback per client IP.
    """

    def __init__(self, app, window_seconds: float | None = None):
        super().__init__(app)
        self.window_seconds = window_seconds

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:
        if getattr(settings, "LOAD_TEST_MODE", False):
            return await call_next(request)

        client_ip = get_real_ip(request)
        user_id, role = extract_jwt_identity(request)

        # Resolve rate limit key and quota
        if user_id:
            identity_key = f"user:{user_id}"
            limit = settings.get_role_rate_limit(role if role else "user")
        elif role:
            identity_key = f"role:{role}"
            limit = settings.get_role_rate_limit(role)
        else:
            identity_key = f"ip:{client_ip}"
            limit = settings.get_role_rate_limit("default")

        window = (
            self.window_seconds
            if self.window_seconds is not None
            else settings.RATE_LIMIT_WINDOW_SECONDS
        )

        allowed, limit_val, remaining_val, retry_after = in_memory_limiter.check_and_update(
            identity_key,
            limit,
            window,
        )

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too Many Requests",
                    "error": "Rate limit exceeded",
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit_val),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit_val)
        response.headers["X-RateLimit-Remaining"] = str(remaining_val)

        return response
