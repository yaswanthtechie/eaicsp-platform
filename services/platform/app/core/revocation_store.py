import hashlib

import redis

from app.core.redis_client import get_redis

REVOCATION_PREFIX = "platform:revoked:"
FAMILY_REVOCATION_PREFIX = "platform:family_revoked:"
FAMILY_ACTIVE_PREFIX = "platform:family_active:"


class RevocationStoreUnavailable(RuntimeError):
    """Raised when Redis cannot be checked for token revocation."""


def _token_key(token: str) -> str:
    """
    Build the Redis key for a revoked access token.

    The raw JWT is never stored directly in Redis keys.
    """
    if not token:
        raise ValueError("Token is required")

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    return f"{REVOCATION_PREFIX}{token_hash}"


def revoke_token(token: str, ttl_seconds: int) -> bool:
    """
    Store an access-token revocation in Redis.

    The entry expires automatically when the access token's
    remaining lifetime expires.

    Returns False if the token, TTL, or Redis operation is invalid.
    """
    if not token or ttl_seconds <= 0:
        return False

    try:
        client = get_redis()
        client.setex(
            _token_key(token),
            int(ttl_seconds),
            "1",
        )
        return True

    except (redis.RedisError, ValueError, TypeError):
        return False


def is_token_revoked(token: str) -> bool:
    """
    Return True only when the token is confirmed revoked.

    Raise RevocationStoreUnavailable when Redis cannot be checked.
    """
    if not token:
        return False

    try:
        client = get_redis()
        return bool(client.exists(_token_key(token)))

    except (redis.RedisError, ValueError, TypeError) as exc:
        raise RevocationStoreUnavailable("Failed to check token revocation") from exc


def clear_revocation(token: str) -> None:
    """
    Remove a token revocation entry.

    Primarily useful for tests. Redis errors are handled gracefully.
    """
    if not token:
        return

    try:
        client = get_redis()
        client.delete(_token_key(token))

    except (redis.RedisError, ValueError, TypeError):
        return


# ============================================================
# TOKEN FAMILY CACHE (REDIS)
# ============================================================


def revoke_family_cache(family_id: str, ttl_seconds: int = 7 * 86400) -> bool:
    """
    Cache family revocation in Redis.
    Also removes the active token pointer for this family.
    Redis errors are handled gracefully (PostgreSQL is source of truth).
    """
    if not family_id or ttl_seconds <= 0:
        return False

    try:
        client = get_redis()
        client.setex(f"{FAMILY_REVOCATION_PREFIX}{family_id}", int(ttl_seconds), "1")
        client.delete(f"{FAMILY_ACTIVE_PREFIX}{family_id}")
        return True
    except (redis.RedisError, ValueError, TypeError):
        return False


def is_family_revoked_in_cache(family_id: str) -> bool:
    """
    Check if a token family is cached as revoked in Redis.
    Returns False on Redis failure or cache miss (safe fallback to PostgreSQL).
    """
    if not family_id:
        return False

    try:
        client = get_redis()
        return bool(client.exists(f"{FAMILY_REVOCATION_PREFIX}{family_id}"))
    except (redis.RedisError, ValueError, TypeError):
        return False


def set_family_active_token(
    family_id: str, token_hash: str, ttl_seconds: int = 7 * 86400
) -> bool:
    """
    Cache the currently active token hash for a token family.
    """
    if not family_id or not token_hash or ttl_seconds <= 0:
        return False

    try:
        client = get_redis()
        client.setex(f"{FAMILY_ACTIVE_PREFIX}{family_id}", int(ttl_seconds), token_hash)
        return True
    except (redis.RedisError, ValueError, TypeError):
        return False


def get_family_active_token(family_id: str) -> str | None:
    """
    Retrieve the active token hash for a family from Redis cache.
    Returns None on cache miss or Redis error (fallback to PostgreSQL).
    """
    if not family_id:
        return None

    try:
        client = get_redis()
        val = client.get(f"{FAMILY_ACTIVE_PREFIX}{family_id}")
        if val is None:
            return None
        if isinstance(val, bytes):
            return val.decode("utf-8")
        return str(val)
    except (redis.RedisError, ValueError, TypeError):
        return None


def clear_family_cache(family_id: str) -> None:
    """
    Clear family revocation and active token cache entries (useful for tests).
    """
    if not family_id:
        return

    try:
        client = get_redis()
        client.delete(f"{FAMILY_REVOCATION_PREFIX}{family_id}")
        client.delete(f"{FAMILY_ACTIVE_PREFIX}{family_id}")
    except (redis.RedisError, ValueError, TypeError):
        return
