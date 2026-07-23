from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# Define global rate limit of 100 requests per minute per IP
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
