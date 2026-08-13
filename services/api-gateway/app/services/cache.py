"""
Thread-safe in-memory cache service for the API Gateway.
"""

import fnmatch
import logging
import threading
import time
from typing import Any

from app.services.metrics import metrics_collector

logger = logging.getLogger("api_gateway.cache")


class InMemoryCache:
    """
    Thread-safe in-memory cache supporting TTL expiration,
    pattern-based invalidation, and metrics collector integration.
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Maps key -> (value, expire_timestamp: float | None)
        self._cache: dict[str, tuple[Any, float | None]] = {}

    def get(
        self,
        key: str,
        service_name: str | None = None,
    ) -> Any | None:
        """
        Get value for `key`. Returns None if missing or expired.
        Automatically updates cache hit/miss metrics if `service_name` is provided.
        """
        now = time.time()
        with self._lock:
            if key in self._cache:
                value, expire_at = self._cache[key]
                if expire_at is None or now < expire_at:
                    if service_name:
                        metrics_collector.record_cache_hit(service_name)
                    return value

                # Expired -> delete
                del self._cache[key]

            if service_name:
                metrics_collector.record_cache_miss(service_name)
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: float | None = None,
    ):
        """
        Set value for `key` with optional TTL in seconds.
        """
        expire_at = (time.time() + ttl_seconds) if ttl_seconds is not None else None
        with self._lock:
            self._cache[key] = (value, expire_at)

    def delete(self, key: str) -> bool:
        """
        Delete a single key from cache. Returns True if key existed.
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching fnmatch `pattern` or string prefix.
        Returns count of keys removed.
        """
        removed_count = 0
        with self._lock:
            keys_to_remove = [
                key for key in self._cache
                if fnmatch.fnmatch(key, pattern) or key.startswith(pattern)
            ]
            for key in set(keys_to_remove):
                del self._cache[key]
                removed_count += 1
        return removed_count

    def clear(self):
        """
        Clear all entries from the cache.
        """
        with self._lock:
            self._cache.clear()


# Singleton in-memory cache instance
cache_service = InMemoryCache()
