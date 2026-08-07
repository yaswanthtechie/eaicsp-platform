"""
Global rate limiter configuration for the API Gateway.
"""

from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware


def get_real_ip(request: Request) -> str:
    """
    Return the client's real IP address.

    If the gateway is running behind a reverse proxy or
    load balancer, the first value from the
    X-Forwarded-For header is used.
    """

    forwarded_for = request.headers.get("X-Forwarded-For")

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return (
        request.client.host
        if request.client
        else "127.0.0.1"
    )


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
