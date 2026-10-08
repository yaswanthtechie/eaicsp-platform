import logging
import os
import re
import time
import uuid
from fastapi import Request
from app.core.logging_config import set_request_id

# ----------------------------------------
# Create logs directory
# ----------------------------------------

os.makedirs("logs", exist_ok=True)

# ----------------------------------------
# Logger
# ----------------------------------------

logger = logging.getLogger("auth_requests")

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

    # ------------------------------------
    # Request ID
    # ------------------------------------

    request_id = request.headers.get(
        "X-Request-ID"
    )

    if not request_id:
        request_id = str(uuid.uuid4())

    request_id = sanitize_log_value(
        request_id,
        "no-request-id",
    )

    # Store request ID in shared logging context.
    set_request_id(request_id)

    # ------------------------------------
    # Service that called Platform
    # ------------------------------------

    caller = request.headers.get(
        "X-Caller-Service",
        "direct-client",
    )

    caller = sanitize_log_value(
        caller,
        "direct-client",
    )

    # ------------------------------------
    # Endpoint in the calling service
    # ------------------------------------

    caller_endpoint = request.headers.get(
        "X-Caller-Endpoint",
        "direct-request",
    )

    caller_endpoint = sanitize_log_value(
        caller_endpoint,
        "direct-request",
    )

    # ------------------------------------
    # Continue request
    # ------------------------------------

    try:
        response = await call_next(request)

    except Exception:
        duration_ms = (
            time.time() - start
        ) * 1000

        logger.exception(
            "HTTP request failed",
            extra={
                "caller": caller,
                "caller_endpoint": caller_endpoint,
                "method": request.method,
                "path": request.url.path,
                "status": 500,
                "duration_ms": round(
                    duration_ms,
                    1,
                ),
            },
        )

        raise

    # ------------------------------------
    # Calculate response time
    # ------------------------------------

    duration_ms = (
        time.time() - start
    ) * 1000

    # ------------------------------------
    # Structured JSON log
    # ------------------------------------

    logger.info(
        "HTTP request completed",
        extra={
            "caller": caller,
            "caller_endpoint": caller_endpoint,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(
                duration_ms,
                1,
            ),
        },
    )

    # ------------------------------------
    # Return request ID to caller
    # ------------------------------------

    response.headers["X-Request-ID"] = request_id

    return response