"""Test-only stand-ins. Production code must never import this module."""


class InMemoryKafkaPublisher:
    """Records published messages instead of sending them to Kafka."""

    def __init__(self, fail_with: Exception | None = None):
        self.published_messages: list[dict] = []
        self.fail_with = fail_with

    def publish(self, topic: str, key: str, value: str) -> bool:
        if self.fail_with is not None:
            raise self.fail_with

        self.published_messages.append(
            {"topic": topic, "key": key, "value": value}
        )
        return True


class FakeRedis:
    """Minimal in-memory stand-in for redis.Redis(decode_responses=True)."""

    def __init__(self):
        self.store: dict[str, str] = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = value
        return True

    def delete(self, *keys):
        return sum(1 for key in keys if self.store.pop(key, None) is not None)

    def scan_iter(self, match="*", count=None):
        prefix = match.rstrip("*")
        return [key for key in list(self.store) if key.startswith(prefix)]

    def ping(self):
        return True
