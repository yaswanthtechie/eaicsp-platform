"""
Global SlowAPI rate limiter configuration and real IP extraction for the API Gateway.

Architecture & Responsibilities:
- `ratelimit.py` (this file): Configures the global SlowAPI IP rate limiter
  (default 100/min per client IP) and provides `get_real_ip()`, which safely
  evaluates `X-Forwarded-For` only when the direct connection peer is listed
  in `settings.TRUSTED_PROXIES` to prevent spoofing.
- `rate_limit.py`: Implements `PerUserRoleRateLimitMiddleware` for JWT-authenticated
  per-user and per-role rate limiting quotas based on validated claims.
"""

from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings


def get_real_ip(request: Request) -> str:
    """
    Return the client's real IP address.

    If the gateway is running behind a reverse proxy or
    load balancer, the first value from the
    X-Forwarded-For header is used ONLY if the immediate
    connection peer (request.client.host) is in TRUSTED_PROXIES.
    Otherwise, request.client.host is returned to prevent rate limit bypass spoofing.
    """
    client_host = request.client.host if request.client else "127.0.0.1"
    trusted_proxies = getattr(settings, "TRUSTED_PROXIES", [])

    if client_host in trusted_proxies:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

    return client_host


# --------------------------------------------------
# Global Rate Limiter
# --------------------------------------------------

limiter = Limiter(
    key_func=get_real_ip,
    default_limits=["100/minute"],
)

__all__ = (
    "RateLimitExceeded",
    "SlowAPIMiddleware",
    "_rate_limit_exceeded_handler",
    "limiter",
)