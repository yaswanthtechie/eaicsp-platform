from collections import defaultdict
from threading import Lock
from time import monotonic

import logging

logger = logging.getLogger(__name__)

VERIFY_MAX_REQUESTS = 100
VERIFY_WINDOW_SECONDS = 60

class VerifyRateLimiter:
    def __init__(
        self,
        max_requests: int = VERIFY_MAX_REQUESTS,
        window_seconds: int = VERIFY_WINDOW_SECONDS,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

        # Stores request timestamps for each caller service
        self._requests = defaultdict(list)

        # Protects the rate-limit data when multiple requests
        # are processed at the same time
        self._lock = Lock()

    def check(self, caller_service: str) -> bool:
        now = monotonic()

        with self._lock:
            requests = self._requests[caller_service]

            # Remove requests outside the current time window
            requests[:] = [
                timestamp
                for timestamp in requests
                if now - timestamp < self.window_seconds
            ]

            logger.debug(
                "Verify rate limit | service=%s current=%s max=%s",
                caller_service,
                len(requests),
                self.max_requests,
            )

            # Block when maximum requests have already been reached
            if len(requests) >= self.max_requests:
                logger.warning(
                    "Verify rate limit BLOCKED for service=%s",
                    caller_service,
                )
                return False

            # Record this request
            requests.append(now)

            return True

    def clear(self):
        """Clear all stored rate-limit data."""
        with self._lock:
            self._requests.clear()


# Single shared rate limiter instance
verify_rate_limiter = VerifyRateLimiter()