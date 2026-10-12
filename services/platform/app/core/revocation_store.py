import hashlib
import redis
from app.core.redis_client import get_redis

REVOCATION_PREFIX = "platform:revoked:"

class RevocationStoreUnavailable(RuntimeError):
    """Raised when Redis cannot be checked for token revocation."""


def _token_key(token: str) -> str:
    """
    Build the Redis key for a revoked access token.

    The raw JWT is never stored directly in Redis keys.
    """
    if not token:
        raise ValueError("Token is required")

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

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
        raise RevocationStoreUnavailable(
            "Failed to check token revocation"
        ) from exc


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
