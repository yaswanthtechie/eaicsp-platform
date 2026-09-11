import time
from typing import Any


class TokenCache:
    def __init__(self, ttl_seconds: int = 60):
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[float, Any]] = {}

    def get(self, token: str):
        entry = self._cache.get(token)

        if entry is None:
            return None

        cached_at, value = entry

        if time.time() - cached_at >= self.ttl_seconds:
            self._cache.pop(token, None)
            return None

        return value

    def set(self, token: str, value: Any):
        self._cache[token] = (time.time(), value)

    def delete(self, token: str):
        self._cache.pop(token, None)

    def clear(self):
        self._cache.clear()


token_cache = TokenCache(ttl_seconds=60)