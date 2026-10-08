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


class FakeKafkaMessage:
    """Stand-in for confluent_kafka.Message."""

    def __init__(
        self,
        value: str | bytes,
        topic: str = "compliance.supplier.status_changed",
        partition: int = 0,
        offset: int = 0,
        error=None,
    ):
        self._value = value.encode("utf-8") if isinstance(value, str) else value
        self._topic = topic
        self._partition = partition
        self._offset = offset
        self._error = error

    def value(self):
        return self._value

    def topic(self):
        return self._topic

    def partition(self):
        return self._partition

    def offset(self):
        return self._offset

    def error(self):
        return self._error


class FakeKafkaConsumer:
    """In-memory Kafka Consumer stand-in for deterministic unit testing."""

    def __init__(self, messages: list[FakeKafkaMessage] | None = None):
        self.messages: list[FakeKafkaMessage] = list(messages) if messages else []
        self.committed_messages: list[FakeKafkaMessage] = []
        self.subscriptions: list[str] = []

    def subscribe(self, topics: list[str]):
        self.subscriptions.extend(topics)

    def poll(self, timeout: float = 1.0):
        if self.messages:
            return self.messages.pop(0)
        return None

    def commit(self, message=None, asynchronous=False):
        if message is not None:
            self.committed_messages.append(message)
