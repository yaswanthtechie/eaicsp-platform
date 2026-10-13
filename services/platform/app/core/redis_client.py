import os
import redis
from redis import Redis

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0",
)

redis_client: Redis = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
)

def get_redis() -> Redis:
    """
    Return the shared Redis client.

    All Platform Service instances must use the same
    REDIS_URL so authentication state is shared.
    """
    return redis_client


def check_redis_connection() -> bool:
    """
    Check whether Redis is reachable.
    """
    try:
        return bool(redis_client.ping())

    except redis.RedisError:
        return False