import json
import logging
import time
from typing import Any, Optional

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

KEY_PREFIX = "inventory:"
BREAKER_COOLDOWN_SECONDS = 30.0


class InventoryCache:
    """
    Redis cache-aside for inventory hot reads.

    Correctness rules:
    - Reads fail open: any Redis error is a cache miss, never a 500.
    - Any Redis error trips a circuit breaker. While it is open the cache
      is bypassed completely, so requests don't each wait for a timeout.
    - When the cooldown ends, every inventory key is wiped BEFORE the cache
      is trusted again. A delete that failed during the outage therefore
      can never serve a stale value afterwards.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_ttl: Optional[int] = None,
    ):
        self.redis_url = redis_url or settings.REDIS_URL
        self.default_ttl = default_ttl or settings.REDIS_CACHE_TTL_SECONDS
        self._client = redis.Redis.from_url(
            self.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        self._down_until: Optional[float] = None

    # ------------------------------------------------------------------
    # Circuit breaker
    # ------------------------------------------------------------------

    def _trip(self, exc: Exception) -> None:
        self._down_until = time.monotonic() + BREAKER_COOLDOWN_SECONDS
        logger.error(
            "Redis unavailable, bypassing cache for %ss: %s",
            BREAKER_COOLDOWN_SECONDS,
            exc,
        )

    def _available(self) -> bool:
        if self._down_until is None:
            return True

        if time.monotonic() < self._down_until:
            return False

        # Cooldown over: anything written before or during the outage may
        # be stale, so wipe all inventory keys before trusting the cache.
        try:
            self._delete_matching(KEY_PREFIX + "*")
        except redis.RedisError as exc:
            self._trip(exc)
            return False

        self._down_until = None
        logger.warning("Redis recovered; flushed inventory keys before re-enabling cache")
        return True

    def _delete_matching(self, pattern: str) -> int:
        # SCAN instead of KEYS: KEYS blocks Redis while it walks every key.
        keys = list(self._client.scan_iter(match=pattern, count=500))
        if not keys:
            return 0
        return int(self._client.delete(*keys))

    # ------------------------------------------------------------------
    # Cache operations
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        if not self._available():
            return None

        try:
            raw = self._client.get(key)
        except redis.RedisError as exc:
            self._trip(exc)
            return None

        if raw is None:
            return None

        try:
            return json.loads(raw)
        except ValueError:
            logger.warning("Corrupt cache value for %s; treating as a miss", key)
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        if not self._available():
            return False

        try:
            self._client.set(
                key,
                json.dumps(value, default=str),
                ex=ttl if ttl is not None else self.default_ttl,
            )
            return True
        except redis.RedisError as exc:
            self._trip(exc)
            return False

    def delete(self, key: str) -> bool:
        if not self._available():
            # Breaker is open; the recovery flush will remove this key.
            return False

        try:
            self._client.delete(key)
            return True
        except redis.RedisError as exc:
            # Tripping guarantees a full flush before the cache is read again.
            self._trip(exc)
            return False

    def delete_pattern(self, pattern: str) -> int:
        if not self._available():
            return 0

        try:
            return self._delete_matching(pattern)
        except redis.RedisError as exc:
            self._trip(exc)
            return 0

    def clear(self) -> None:
        """Remove every inventory key (used by tests and tooling)."""
        self.delete_pattern(KEY_PREFIX + "*")


# Global singleton instance
cache = InventoryCache()


import threading
import time


def make_item_key(sku_id: str, warehouse_id: str) -> str:
    return f"inventory:item:{sku_id}:{warehouse_id}"


# Fence keys live OUTSIDE the "inventory:" prefix on purpose: a bulk
# invalidation deletes "inventory:*", and deleting the fences with the data
# would reset them and let an in-flight read cache an old value.
META_PREFIX = "inventory_meta:"


def make_version_key(sku_id: str, warehouse_id: str) -> str:
    return f"{META_PREFIX}min_ver:{sku_id}:{warehouse_id}"


ALL_ITEMS_KEY = "inventory:all"
ALL_ITEMS_GEN_KEY = f"{META_PREFIX}all:gen"


def get_all_inventory_generation() -> int:
    """Return the current generation counter for the all-inventory collection."""
    try:
        raw = cache.get(ALL_ITEMS_GEN_KEY)
        return int(raw) if raw is not None else 0
    except Exception:
        return 0


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
) -> bool:
    """
    Store inventory response payload in cache with optimistic concurrency protection.
    Prevents cache-aside race conditions where a concurrent read writes a stale value
    after an update committed and deleted the key.
    """
    try:
        version_key = make_version_key(sku_id, warehouse_id)
        item_version = data.get("version")
        if item_version is not None:
            min_ver = cache.get(version_key)
            if min_ver is not None and int(item_version) < int(min_ver):
                logger.debug(
                    "Rejected stale cache write for %s:%s (version %s < min_version %s)",
                    sku_id,
                    warehouse_id,
                    item_version,
                    min_ver,
                )
                return False

        key = make_item_key(sku_id, warehouse_id)
        # Also prevent overwriting if existing cached value is newer
        existing = cache.get(key)
        if existing and item_version is not None:
            existing_ver = existing.get("version")
            if existing_ver is not None and int(existing_ver) > int(item_version):
                return False

        cache.set(key, data, ttl=ttl)
        return True
    except Exception as exc:
        logger.debug("Failed to set cached inventory: %s", exc)
        return False


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
    generation: Optional[int] = None,
) -> bool:
    """
    Store full inventory list in cache.
    If generation is provided, ensures no concurrent update invalidated the
    collection while the list was being fetched from the database.
    """
    try:
        if generation is not None:
            current_gen = get_all_inventory_generation()
            if current_gen != generation:
                logger.debug(
                    "Rejected stale all-inventory cache write (generation %s != %s)",
                    generation,
                    current_gen,
                )
                return False

        cache.set(ALL_ITEMS_KEY, data, ttl=ttl)
        return True
    except Exception as exc:
        logger.debug("Failed to set cached all inventory: %s", exc)
        return False


def invalidate_inventory_cache(
    sku_id: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    version: Optional[int] = None,
) -> None:
    """
    Invalidate inventory cache upon mutation.
    
    Rules:
    - If sku_id and warehouse_id are provided:
      1. Invalidate single-item cache: 'inventory:item:{sku_id}:{warehouse_id}'
      2. Record min_version fence to reject race-condition writes of older versions
      3. Invalidate collection cache: 'inventory:all' and increment generation counter
      4. Trigger delayed second delete to clean up any in-flight reads (delayed double-delete)
    - If not provided (bulk mutations / upload / widespread changes):
      Invalidate all 'inventory:*' keys.
    """
    try:
        # Any write invalidates the global collection
        cache.delete(ALL_ITEMS_KEY)
        curr_gen = get_all_inventory_generation()
        cache.set(ALL_ITEMS_GEN_KEY, curr_gen + 1, ttl=300)

        if sku_id and warehouse_id:
            item_key = make_item_key(sku_id, warehouse_id)
            cache.delete(item_key)

            # Update version fence. Every caller must pass the committed
            # version; a guessed number can be too low (stale reads get
            # through) or too high (the item is never cached again).
            version_key = make_version_key(sku_id, warehouse_id)
            if version is not None:
                cache.set(version_key, version, ttl=300)
            else:
                logger.warning(
                    "invalidate_inventory_cache(%s, %s) called without version; "
                    "relying on the delayed delete only",
                    sku_id,
                    warehouse_id,
                )

            logger.debug("Invalidated cache for %s:%s and collection", sku_id, warehouse_id)

            # Delayed double-delete to eliminate concurrent read-write race window
            def _delayed_delete():
                time.sleep(0.2)
                try:
                    cache.delete(item_key)
                    cache.delete(ALL_ITEMS_KEY)
                except Exception:
                    pass

            threading.Thread(target=_delayed_delete, daemon=True).start()
        else:
            cache.delete_pattern("inventory:*")
            logger.debug("Invalidated all inventory cache keys")
    except Exception as exc:
        logger.debug("Failed to invalidate cache: %s", exc)
