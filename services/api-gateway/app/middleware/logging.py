"""
Custom logging middleware for the API Gateway.
"""

import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# --------------------------------------------------
# Configure Logging
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("api_gateway.access")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log every incoming HTTP request and response.

    Logs:
    - HTTP Method
    - Request Path
    - Status Code
    - Response Time
    - Client IP
    """

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = response.status_code

        except Exception:
            status_code = 500
            raise

        finally:
            process_time_ms = (
                time.perf_counter() - start_time
            ) * 1000

            method = request.method
            path = request.url.path

            forwarded_for = request.headers.get("X-Forwarded-For")

            if forwarded_for:
                client_ip = forwarded_for.split(",")[0].strip()
            else:
                client_ip = (
                    request.client.host
                    if request.client
                    else "unknown"
                )

            logger.info(
                "method=%s path=%s status=%s duration=%.2fms ip=%s",
                method,
                path,
                status_code,
                process_time_ms,
                client_ip,
            )

        return response