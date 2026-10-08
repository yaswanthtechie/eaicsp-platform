'''from dataclasses import dataclass
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
)'''

"""
Redis-backed JWT verification cache for Platform Service.

Round 12+13 - Milestone 1

The cache is shared by all Platform Service instances connected
to the same Redis server.

Features:
- Redis-backed verification cache
- Redis TTL
- SHA-256 token keys
- User-level cache invalidation
- Redis user index for efficient invalidation
- Graceful Redis failure handling
- Backward-compatible TokenCache public API
- No raw JWT stored in Redis keys

Redis keys:

    platform:verify:<sha256(token)>

    platform:verify:user:<user_id>

The raw JWT is never used directly as a Redis key.
"""

import hashlib
import json
from typing import Any

import redis

from app.core.redis_client import get_redis


class TokenCache:
    """
    Redis-backed JWT verification cache.

    The cache is shared between multiple Platform Service
    instances through Redis.

    Main responsibilities:

    1. Cache successful /verify responses.
    2. Automatically expire cached entries using Redis TTL.
    3. Track cached tokens by user.
    4. Invalidate all cached tokens for a user when their
       security-sensitive state changes.
    5. Treat Redis failures as cache misses instead of
       breaking authentication.

    Redis key structure:

        platform:verify:<sha256(token)>
        platform:verify:user:<user_id>

    The raw JWT is never stored inside a Redis key.
    """

    KEY_PREFIX = "platform:verify:"
    USER_INDEX_PREFIX = "platform:verify:user:"

    def __init__(
        self,
        ttl_seconds: int = 60,
        max_entries: int = 10_000,
    ):
        """
        Initialize the token cache.

        Args:
            ttl_seconds:
                Default Redis TTL for verification cache entries.

            max_entries:
                Retained for backward compatibility with the
                previous in-memory implementation.

                Redis itself is responsible for memory management
                and eviction, so this value is not used to manually
                evict entries.
        """
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries

    # ============================================================
    # KEY HELPERS
    # ============================================================

    def _make_key(self, token: str) -> str:
        """
        Create a Redis key for a JWT.

        The raw JWT is never stored as the Redis key.

        Example:

            platform:verify:<sha256(token)>
        """

        if not token:
            raise ValueError("Token cannot be None or empty")

        token_hash = hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()

        return f"{self.KEY_PREFIX}{token_hash}"

    def _make_user_key(self, user_id: int) -> str:
        """
        Create the Redis user-index key.

        Example:

            platform:verify:user:123
        """

        return f"{self.USER_INDEX_PREFIX}{user_id}"

    # ============================================================
    # GET
    # ============================================================

    def get(
        self,
        token: str,
    ) -> dict[str, Any] | None:
        """
        Return a cached verification response.

        Returns:
            Cached verification response on cache hit.
            None on cache miss, expiration, malformed data,
            or Redis failure.

        Redis failure is deliberately treated as a cache miss.

        This means the authentication flow can fall back to
        normal JWT + database verification.
        """

        # A missing token is a cache miss, not a Redis error.
        if not token:
            return None

        client = get_redis()

        try:
            key = self._make_key(token)
            raw_value = client.get(key)

            if raw_value is None:
                return None

            cached = json.loads(raw_value)

            return cached["value"]

        except (
            redis.RedisError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ):
            return None

    # ============================================================
    # SET
    # ============================================================

    def set(
        self,
        token: str,
        value: dict[str, Any],
        user_id: int,
        ttl_seconds: int | None = None,
    ) -> None:
        """
        Store a verification response in Redis.

        Args:
            token:
                JWT being cached.

            value:
                Verification response.

            user_id:
                User associated with the JWT.

            ttl_seconds:
                Optional custom TTL.

        The caller should ensure that the TTL does not exceed
        the remaining lifetime of the JWT.
        """

        if not token:
            return

        ttl = (
            self.ttl_seconds
            if ttl_seconds is None
            else ttl_seconds
        )

        if ttl <= 0:
            return

        client = get_redis()

        try:
            token_key = self._make_key(token)
            user_key = self._make_user_key(user_id)

            payload = {
                "value": value,
                "user_id": user_id,
            }

            # ----------------------------------------------------
            # Store token verification result.
            # ----------------------------------------------------

            client.setex(
                token_key,
                int(ttl),
                json.dumps(payload),
            )

            # ----------------------------------------------------
            # Maintain user -> token membership.
            #
            # This allows invalidate_user() to find all cached
            # tokens belonging to a user.
            # ----------------------------------------------------

            client.sadd(
                user_key,
                token_key,
            )

            # ----------------------------------------------------
            # Keep the user index slightly longer than the token
            # cache entry.
            # ----------------------------------------------------

            client.expire(
                user_key,
                int(ttl) + 60,
            )

        except (
            redis.RedisError,
            ValueError,
            TypeError,
        ):
            # Redis is a cache.
            #
            # A Redis failure must never make a valid JWT
            # unusable.
            return

    # ============================================================
    # DELETE
    # ============================================================

    def delete(
        self,
        token: str,
    ) -> None:
        """
        Delete one cached token.

        This method also removes the token from its user index
        when the cached payload is available.
        """

        if not token:
            return

        client = get_redis()

        try:
            token_key = self._make_key(token)

            # ----------------------------------------------------
            # Read the cached entry first so that we know the
            # associated user_id.
            # ----------------------------------------------------

            raw_value = client.get(token_key)

            if raw_value is not None:
                try:
                    cached = json.loads(raw_value)
                    user_id = cached.get("user_id")

                    if user_id is not None:
                        user_key = self._make_user_key(user_id)

                        client.srem(
                            user_key,
                            token_key,
                        )

                except (
                    json.JSONDecodeError,
                    TypeError,
                    AttributeError,
                ):
                    # If the cached payload is malformed,
                    # continue deleting the token itself.
                    pass

            client.delete(token_key)

        except (
            redis.RedisError,
            ValueError,
        ):
            return

    # ============================================================
    # INVALIDATE USER
    # ============================================================

    def invalidate_user(
        self,
        user_id: int,
    ) -> None:
        """
        Delete all verification cache entries belonging to a user.

        Used when security-sensitive user state changes, such as:

        - Account deactivation
        - Account lock
        - Password reset
        - Role change
        - Other authentication/security state changes
        """

        client = get_redis()

        user_key = self._make_user_key(user_id)

        try:
            # ----------------------------------------------------
            # Get all cached token keys belonging to this user.
            # ----------------------------------------------------

            token_keys = client.smembers(user_key)

            if token_keys:
                client.delete(*token_keys)

            # ----------------------------------------------------
            # Remove the user index itself.
            # ----------------------------------------------------

            client.delete(user_key)

        except redis.RedisError:
            # Cache invalidation failure should not crash
            # the authentication request.
            return

    # ============================================================
    # SIZE
    # ============================================================

    def size(self) -> int:
        """
        Return the number of verification cache entries.

        User-index keys are excluded.

        This method is mainly intended for diagnostics and tests.

        Redis SCAN is used instead of KEYS so that we do not
        block Redis while scanning a large keyspace.
        """

        client = get_redis()

        try:
            count = 0

            for key in client.scan_iter(
                match=f"{self.KEY_PREFIX}*"
            ):
                # Exclude user-index keys.
                if isinstance(key, bytes):
                    key = key.decode("utf-8")

                if key.startswith(self.USER_INDEX_PREFIX):
                    continue

                count += 1

            return count

        except redis.RedisError:
            return 0

    # ============================================================
    # CLEAR
    # ============================================================

    def clear(self) -> None:
        """
        Clear all Platform verification cache entries,
        including user indexes.

        This is mainly useful for tests, diagnostics,
        and controlled cache maintenance.
        """

        client = get_redis()

        try:
            keys = list(
                client.scan_iter(
                    match=f"{self.KEY_PREFIX}*"
                )
            )

            if keys:
                client.delete(*keys)

        except redis.RedisError:
            return


# ================================================================
# GLOBAL TOKEN CACHE
# ================================================================

token_cache = TokenCache(
    ttl_seconds=60,
    max_entries=10_000,
)