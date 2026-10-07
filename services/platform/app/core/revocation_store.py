import hashlib
import redis
from app.core.redis_client import get_redis

REVOCATION_PREFIX = "platform:revoked:"

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

def revoke_token(
    token: str,
    ttl_seconds: int,
) -> bool:
    """
    Store an access-token revocation in Redis.

    The Redis entry expires automatically when the access
    token's remaining lifetime expires.
    """
    if not token:
        return False

    if ttl_seconds <= 0:
        return False

    client = get_redis()

    try:
        client.setex(
            _token_key(token),
            int(ttl_seconds),
            "1",
        )
        return True

    except (redis.RedisError, ValueError):
        return False

def is_token_revoked(token: str) -> bool:
    """
    Return True when the access token is revoked.

    Redis errors fail closed because revocation is
    security-sensitive state.
    """
    if not token:
        return False

    client = get_redis()

    try:
        return client.exists(
            _token_key(token)
        ) == 1

    except (redis.RedisError, ValueError):
        return True


def clear_revocation(token: str) -> None:
    """
    Remove a token revocation entry.

    Primarily useful for tests.
    """
    if not token:
        return

    client = get_redis()

    try:
        client.delete(
            _token_key(token)
        )

    except (redis.RedisError, ValueError):
        return