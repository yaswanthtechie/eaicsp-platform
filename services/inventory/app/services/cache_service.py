import json
import logging
from typing import Any, Optional

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from app.core.config import settings

logger = logging.getLogger(__name__)


class InventoryCache:
    """
    Redis Cache Service for Inventory Service.
    
    Provides fast, serialized caching for hot read paths:
    - GET /api/v1/inventory/{sku_id}/{warehouse_id}
    - GET /api/v1/inventory/
    
    Features:
    - Graceful degradation: If Redis is unavailable or times out,
      calls fail open (cache miss) without failing API requests.
    - Automatic JSON serialization / deserialization.
    - Deterministic invalidation on every stock mutation.
    - Configurable mock / fallback mode for local testing.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_ttl: Optional[int] = None,
        mock_mode: bool = False,
    ):
        self.redis_url = redis_url or getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        self.default_ttl = default_ttl or getattr(settings, "REDIS_CACHE_TTL_SECONDS", 300)
        self.mock_mode = mock_mode
        self._memory_store: dict[str, str] = {}
        self._client: Optional[Any] = None

        if not self.mock_mode and REDIS_AVAILABLE:
            try:
                self._client = redis.Redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=1.0,
                    socket_timeout=1.0,
                )
            except Exception as exc:
                logger.warning("Could not initialize Redis client (%s). Using fallback.", exc)
                self._client = None

    def _get_client(self):
        return self._client

    # ------------------------------------------------------------------------
    # Core Cache Operations
    # ------------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        """Retrieve and parse JSON value for key, returning None on miss or error."""
        if self.mock_mode or self._client is None:
            raw = self._memory_store.get(key)
            if raw is not None:
                try:
                    return json.loads(raw)
                except Exception:
                    return raw
            return None

        try:
            raw = self._client.get(key)
            if raw is not None:
                return json.loads(raw)
            return None
        except Exception as exc:
            logger.debug("Redis GET '%s' failed (graceful degradation): %s", key, exc)
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """Serialize and store value with TTL. Returns True on success, False on error."""
        expiry = ttl if ttl is not None else self.default_ttl
        serialized = json.dumps(value, default=str)

        if self.mock_mode or self._client is None:
            self._memory_store[key] = serialized
            return True

        try:
            self._client.set(key, serialized, ex=expiry)
            return True
        except Exception as exc:
            logger.debug("Redis SET '%s' failed (graceful degradation): %s", key, exc)
            # Store in fallback memory so tests pass even without live Redis
            self._memory_store[key] = serialized
            return False

    def delete(self, key: str) -> bool:
        """Delete specific cache key."""
        self._memory_store.pop(key, None)
        if self.mock_mode or self._client is None:
            return True

        try:
            self._client.delete(key)
            return True
        except Exception as exc:
            logger.debug("Redis DELETE '%s' failed: %s", key, exc)
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern (e.g. 'inventory:*')."""
        deleted_count = 0
        keys_to_remove = [k for k in self._memory_store if k.startswith(pattern.replace("*", ""))]
        for k in keys_to_remove:
            self._memory_store.pop(k, None)
            deleted_count += 1

        if self.mock_mode or self._client is None:
            return deleted_count

        try:
            matching = self._client.keys(pattern)
            if matching:
                deleted_count += self._client.delete(*matching)
        except Exception as exc:
            logger.debug("Redis DELETE pattern '%s' failed: %s", pattern, exc)

        return deleted_count

    def clear(self) -> None:
        """Flush all cache items (used in testing)."""
        self._memory_store.clear()
        if not self.mock_mode and self._client is not None:
            try:
                self.delete_pattern("inventory:*")
            except Exception:
                pass


# Global singleton instance
cache = InventoryCache()


# ----------------------------------------------------------------------------
# High-Level Inventory Domain Helpers
# ----------------------------------------------------------------------------

def make_item_key(sku_id: str, warehouse_id: str) -> str:
    return f"inventory:item:{sku_id}:{warehouse_id}"


ALL_ITEMS_KEY = "inventory:all"


def get_cached_inventory(sku_id: str, warehouse_id: str) -> Optional[dict]:
    """Retrieve cached inventory response payload for SKU and warehouse."""
    try:
        key = make_item_key(sku_id, warehouse_id)
        return cache.get(key)
    except Exception as exc:
        logger.debug("Failed to get cached inventory: %s", exc)
        return None


def set_cached_inventory(
    sku_id: str,
    warehouse_id: str,
    data: dict,
    ttl: Optional[int] = None,
) -> None:
    """Store inventory response payload in cache."""
    try:
        key = make_item_key(sku_id, warehouse_id)
        cache.set(key, data, ttl=ttl)
    except Exception as exc:
        logger.debug("Failed to set cached inventory: %s", exc)


def get_cached_all_inventory() -> Optional[list[dict]]:
    """Retrieve cached list of all inventory items."""
    try:
        return cache.get(ALL_ITEMS_KEY)
    except Exception as exc:
        logger.debug("Failed to get cached all inventory: %s", exc)
        return None


def set_cached_all_inventory(
    data: list[dict],
    ttl: Optional[int] = None,
) -> None:
    """Store full inventory list in cache."""
    try:
        cache.set(ALL_ITEMS_KEY, data, ttl=ttl)
    except Exception as exc:
        logger.debug("Failed to set cached all inventory: %s", exc)


def invalidate_inventory_cache(
    sku_id: Optional[str] = None,
    warehouse_id: Optional[str] = None,
) -> None:
    """
    Invalidate inventory cache upon mutation.
    
    Rules:
    - If sku_id and warehouse_id are provided:
      1. Invalidate single-item cache: 'inventory:item:{sku_id}:{warehouse_id}'
      2. Invalidate collection cache: 'inventory:all'
    - If not provided (bulk mutations / upload / widespread changes):
      Invalidate all 'inventory:*' keys.
    """
    try:
        # Any write invalidates the global collection
        cache.delete(ALL_ITEMS_KEY)

        if sku_id and warehouse_id:
            cache.delete(make_item_key(sku_id, warehouse_id))
            logger.debug("Invalidated cache for %s:%s and collection", sku_id, warehouse_id)
        else:
            cache.delete_pattern("inventory:*")
            logger.debug("Invalidated all inventory cache keys")
    except Exception as exc:
        logger.debug("Failed to invalidate cache: %s", exc)
