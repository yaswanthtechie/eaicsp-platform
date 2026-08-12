"""
Global rate limiter configuration for the API Gateway.
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
    "limiter",
    "RateLimitExceeded",
    "_rate_limit_exceeded_handler",
    "SlowAPIMiddleware",
)