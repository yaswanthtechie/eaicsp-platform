"""
Unit tests for the thread-safe InMemoryCache service.
"""

import threading
import time

import pytest

from app.services.cache import InMemoryCache, cache_service
from app.services.metrics import metrics_collector


@pytest.fixture(autouse=True)
def reset_cache_and_metrics():
    """Reset cache and metrics collector before and after each test."""
    cache_service.clear()
    metrics_collector.reset()
    yield
    cache_service.clear()
    metrics_collector.reset()


def test_cache_set_and_get():
    """
    Test storing and retrieving values from the cache.
    """
    cache = InMemoryCache()
    cache.set("user:123", {"name": "Alice"})

    val = cache.get("user:123")
    assert val == {"name": "Alice"}

    assert cache.get("nonexistent") is None


def test_cache_ttl_expiration():
    """
    Test that cached entries expire after configured TTL.
    """
    cache = InMemoryCache()
    cache.set("temp_key", "temp_val", ttl_seconds=0.1)

    assert cache.get("temp_key") == "temp_val"

    time.sleep(0.15)

    assert cache.get("temp_key") is None


def test_cache_delete_and_clear():
    """
    Test single key deletion and clearing full cache.
    """
    cache = InMemoryCache()
    cache.set("key1", "val1")
    cache.set("key2", "val2")

    deleted = cache.delete("key1")
    assert deleted is True
    assert cache.get("key1") is None
    assert cache.get("key2") == "val2"

    assert cache.delete("key1") is False

    cache.clear()
    assert cache.get("key2") is None


def test_cache_invalidation_by_pattern():
    """
    Test invalidating cache entries by prefix and fnmatch pattern.
    """
    cache = InMemoryCache()
    cache.set("inventory:item:1", "data1")
    cache.set("inventory:item:2", "data2")
    cache.set("shipments:order:1", "data3")

    # Invalidate by prefix
    count = cache.invalidate_pattern("inventory:*")
    assert count == 2
    assert cache.get("inventory:item:1") is None
    assert cache.get("inventory:item:2") is None
    assert cache.get("shipments:order:1") == "data3"


def test_cache_metrics_integration():
    """
    Test that cache GET operations record cache hits and misses in metrics_collector.
    """
    cache = InMemoryCache()
    cache.set("inventory:1", "item_data")

    # Hit
    val = cache.get("inventory:1", service_name="inventory")
    assert val == "item_data"

    # Miss
    val_miss = cache.get("inventory:999", service_name="inventory")
    assert val_miss is None

    metrics = metrics_collector.get_all_metrics()
    inv_metrics = metrics["services"]["inventory"]
    assert inv_metrics["cache_hit_rate"] == 50.0


def test_cache_thread_safety():
    """
    Test concurrent reads and writes across multiple threads.
    """
    cache = InMemoryCache()
    num_threads = 10
    iterations = 50

    def worker(thread_id: int):
        for i in range(iterations):
            key = f"key_{thread_id}_{i}"
            cache.set(key, i)
            val = cache.get(key)
            assert val == i
            cache.delete(key)

    threads = [
        threading.Thread(target=worker, args=(t,))
        for t in range(num_threads)
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert cache.get("key_0_0") is None
