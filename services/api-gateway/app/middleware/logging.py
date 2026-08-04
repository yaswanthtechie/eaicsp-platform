import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Configure production-style logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("api_gateway.access")

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            # Capture status code 500 for unhandled exceptions before raising
            status_code = 500
            raise e
        finally:
            # Calculate duration in milliseconds
            process_time_ms = (time.time() - start_time) * 1000
            
            # Extract request details
            method = request.method
            path = request.url.path
            
            # Get client IP, respecting proxy headers if they exist
            client_ip = request.client.host if request.client else "unknown"
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                client_ip = forwarded_for.split(",")[0].strip()
                
            # Log structured access data
            logger.info(
                f"method={method} path={path} status={status_code} "
                f"duration={process_time_ms:.2f}ms ip={client_ip}"
            )
            
        return response
