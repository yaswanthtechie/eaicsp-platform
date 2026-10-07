import logging
import os
#import re
import time
from fastapi import Request
 
# ----------------------------------------
# Create logs directory
# ----------------------------------------
 
os.makedirs("logs", exist_ok=True)
 
# ----------------------------------------
# Logging configuration
# ----------------------------------------
 
logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
    handlers=[
        logging.FileHandler(
            "logs/auth_requests.log"
        ),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(
    "auth_requests"
)

# ----------------------------------------
# JWT / token detection
# ----------------------------------------
JWT_PATTERN = re.compile(
    r"^eyJ[A-Za-z0-9_-]+\."
    r"[A-Za-z0-9_-]+\."
    r"[A-Za-z0-9_-]+$"
)
def sanitize_log_value(
    value: str | None,
    default: str,
) -> str:
    """
    Prevent sensitive authentication tokens from
    being written to application logs.

    If the value looks like a JWT, it is replaced
    with a safe label.
    """

    if not value:
        return default

    value = value.strip()

    if JWT_PATTERN.match(value):
        return "authenticated-client"

    # Also protect obvious Bearer token values.
    if value.lower().startswith("bearer "):
        return "authenticated-client"

    return value
# ----------------------------------------
# Request logging middleware
# ----------------------------------------
 
async def log_requests(
    request: Request,
    call_next,
):
    start = time.time()
 
    # Calling Service
    caller = request.headers.get(
        "X-Caller-Service",
        "direct-client",
    )
    caller = sanitize_log_value(
        caller,
        "direct-client",
    )
 
    # Calling Endpoint
    caller_endpoint = request.headers.get(
        "X-Caller-Endpoint",
        "direct-request",
    )

    caller_endpoint = sanitize_log_value(
        caller_endpoint,
        "direct-request",
    )
 
    # Request ID
    request_id = request.headers.get(
        "X-Request-ID",
        "no-id",
    )
    request_id = sanitize_log_value(
        request_id,
        "no-id",
    )
 
    # Continue request
    response = await call_next(
        request
    )
 
    # Calculate response time
    duration_ms = (
        time.time() - start
    ) * 1000
 
    # Log request
    logger.info(
        "caller=%s "
        "caller_endpoint=%s "
        "request_id=%s "
        "method=%s "
        "path=%s "
        "status=%s "
        "duration_ms=%.1f",
        caller,
        caller_endpoint,
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
 
    return response

