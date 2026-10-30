"""
Deduplication service for Realtime WebSocket (R15-M3).

Maintains a bounded sliding-window cache of deduplication keys to prevent
re-broadcasting duplicate messages during transient broker replays and reconnects.

Deduplication rules:
- 'iot.anomaly.detected': deduplicates on payload.episode_id (replay publishes new event_id for same episode)
- All other event types: deduplicates on event_id

Delivery semantics:
Kafka provides at-least-once delivery. The BFF deduplicator provides bounded,
best-effort idempotency over a sliding window (default 1,000 keys). It does not
claim global exactly-once delivery across arbitrary multi-node gateways or restarts.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
import logging
from typing import Optional

logger = logging.getLogger("api_gateway.realtime.deduplicator")


class Deduplicator:
    """
    Thread- and async-safe bounded deduplication cache using an OrderedDict.
    """

    def __init__(self, max_size: int = 1000) -> None:
        self.max_size = max(1, max_size)
        self._cache: OrderedDict[str, None] = OrderedDict()
        self._lock = asyncio.Lock()

    async def is_duplicate(self, dedup_key: str) -> bool:
        """
        Check if the key has already been seen in the deduplication window.
        If seen, returns True.
        If not seen, records the key, evicts the oldest entry if capacity is exceeded,
        and returns False.
        """
        if not dedup_key:
            return False

        async with self._lock:
            if dedup_key in self._cache:
                logger.debug("Duplicate event dropped for dedup_key=%s", dedup_key)
                return True

            self._cache[dedup_key] = None
            if len(self._cache) > self.max_size:
                self._cache.popitem(last=False)
            return False

    async def contains(self, dedup_key: str) -> bool:
        """Read-only check whether key exists in cache without inserting."""
        async with self._lock:
            return dedup_key in self._cache

    async def clear(self) -> None:
        """Clear the cache (useful between tests)."""
        async with self._lock:
            self._cache.clear()

    async def size(self) -> int:
        """Return current number of cached keys."""
        async with self._lock:
            return len(self._cache)
