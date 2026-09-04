import logging
import os
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
# Request logging middleware
# ----------------------------------------
 
async def log_requests(
    request: Request,
    call_next,
):
    start = time.time()
 
    # Service that called Rahul
    caller = request.headers.get(
        "X-Caller-Service",
        "direct-client",
    )
 
    # Endpoint in the calling service
    caller_endpoint = request.headers.get(
        "X-Caller-Endpoint",
        "direct-request",
    )
 
    # Request ID
    request_id = request.headers.get(
        "X-Request-ID",
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
 