from dataclasses import dataclass
from time import monotonic
from threading import RLock
from collections import OrderedDict
from typing import Any

@dataclass
class CacheEntry:
    """
    Cached token verification result.
    """
    value: dict[str, Any]
    user_id: int
    expires_at: float

class TokenCache:
    """
    In-memory cache for JWT verification results.

    Features:
    - 60-second TTL by default
    - Token -> user mapping
    - User-level invalidation
    - Maximum cache size
    - Thread-safe access
    - Expired-entry cleanup
    - LRU eviction
    """

    def __init__(
        self,
        ttl_seconds: int = 60,
        max_entries: int = 10_000,
    ):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries

        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = RLock()

    def get(self, token: str) -> dict[str, Any] | None:
        """
        Return cached verification response if valid.

        Returns:
            Cached response on cache hit.
            None on cache miss or expired entry.
        """
        with self._lock:
            entry = self._cache.get(token)

            if entry is None:
                return None

            # Remove expired entry
            if monotonic() >= entry.expires_at:
                self._cache.pop(token, None)
                return None

            # Mark token as recently used
            self._cache.move_to_end(token)

            return entry.value

    def set(
        self,
        token: str,
        value: dict[str, Any],
        user_id: int,
        ttl_seconds: int | None = None,
    ) -> None:
        """
        Store a token verification response.

        The TTL can be overridden for an individual token.
        This allows the cache lifetime to never exceed the
        JWT's remaining lifetime.
        """
        ttl = (
            self.ttl_seconds
            if ttl_seconds is None
            else ttl_seconds
        )

        if ttl <= 0:
            return

        with self._lock:
            # Replace existing entry if present
            self._cache.pop(token, None)

            # Prevent unlimited memory growth.
            # Remove least-recently-used entries first.
            while len(self._cache) >= self.max_entries:
                self._cache.popitem(last=False)

            self._cache[token] = CacheEntry(
                value=value,
                user_id=user_id,
                expires_at=monotonic() + ttl,
            )

    def delete(self, token: str) -> None:
        """
        Remove one token from the cache.
        """
        with self._lock:
            self._cache.pop(token, None)

    def invalidate_user(self, user_id: int) -> None:
        """
        Remove every cached token belonging to a user.

        This is important when user security state changes:

        - User is deactivated
        - User role changes
        - Password is reset
        - Account is locked
        """
        with self._lock:
            tokens_to_remove = [
                token
                for token, entry in self._cache.items()
                if entry.user_id == user_id
            ]

            for token in tokens_to_remove:
                self._cache.pop(token, None)

    def clear(self) -> None:
        """
        Clear the entire token cache.
        """
        with self._lock:
            self._cache.clear()

    def cleanup(self) -> None:
        """
        Remove all expired cache entries.

        Useful for periodic maintenance because expired
        entries that are never requested again would otherwise
        remain until LRU eviction.
        """
        now = monotonic()

        with self._lock:
            expired_tokens = [
                token
                for token, entry in self._cache.items()
                if now >= entry.expires_at
            ]

            for token in expired_tokens:
                self._cache.pop(token, None)

    def size(self) -> int:
        """
        Return the current number of cached entries.
        """
        with self._lock:
            return len(self._cache)


# Global token cache used by the Platform Service
token_cache = TokenCache(
    ttl_seconds=60,
    max_entries=10_000,
)