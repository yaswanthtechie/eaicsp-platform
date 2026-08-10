"""
Custom logging middleware for the API Gateway.
"""

import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.middleware.ratelimit import get_real_ip

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

            request_id = getattr(request.state, "request_id", None)
            method = request.method
            path = request.url.path

            client_ip = get_real_ip(request)

            logger.info(
                "request_id=%s method=%s path=%s status=%s duration=%.2fms ip=%s",
                request_id,
                method,
                path,
                status_code,
                process_time_ms,
                client_ip,
            )

        return response