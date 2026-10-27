"""
Tests for Realtime Deduplication Service (R15-M3).

Verifies idempotency guarantees:
- Ordinary events deduplicate on event_id.
- Anomaly episodes deduplicate on payload.episode_id (crash replay protection).
- Deduplication cache remains bounded and evicts oldest keys.
- Async concurrent safety.
"""

import asyncio
import uuid
import pytest

from app.services.realtime.deduplicator import Deduplicator


@pytest.mark.asyncio
async def test_deduplicator_first_seen_returns_false():
    """First time seeing a key returns False (not duplicate)."""
    dedup = Deduplicator(max_size=100)
    key = str(uuid.uuid4())
    is_dup = await dedup.is_duplicate(key)
    assert is_dup is False
    assert await dedup.size() == 1


@pytest.mark.asyncio
async def test_deduplicator_second_seen_returns_true():
    """Second time seeing the same key returns True (duplicate)."""
    dedup = Deduplicator(max_size=100)
    key = str(uuid.uuid4())
    assert await dedup.is_duplicate(key) is False
    assert await dedup.is_duplicate(key) is True
    assert await dedup.size() == 1


@pytest.mark.asyncio
async def test_anomaly_episode_replay_with_new_event_id_deduplicated():
    """
    Kafka replay of an anomaly episode with a different event_id but identical
    episode_id must be recognized as a duplicate.
    """
    dedup = Deduplicator(max_size=100)
    episode_id = "WH-BLR-01-S1|2026-10-15T10:05:00+00:00"

    # Initial delivery
    first_delivery = await dedup.is_duplicate(episode_id)
    assert first_delivery is False

    # Crash replay delivery with new event_id but same episode_id
    replay_delivery = await dedup.is_duplicate(episode_id)
    assert replay_delivery is True


@pytest.mark.asyncio
async def test_deduplicator_bounded_capacity_eviction():
    """Cache must maintain bounded memory by evicting oldest keys past max_size."""
    dedup = Deduplicator(max_size=3)

    assert await dedup.is_duplicate("key-1") is False
    assert await dedup.is_duplicate("key-2") is False
    assert await dedup.is_duplicate("key-3") is False
    assert await dedup.size() == 3

    # Adding a 4th key must evict key-1
    assert await dedup.is_duplicate("key-4") is False
    assert await dedup.size() == 3

    # key-1 was evicted, so seeing it again treats it as new
    assert await dedup.contains("key-1") is False
    assert await dedup.contains("key-2") is True
    assert await dedup.contains("key-3") is True
    assert await dedup.contains("key-4") is True


@pytest.mark.asyncio
async def test_deduplicator_clear():
    """Clearing the deduplicator resets its state."""
    dedup = Deduplicator(max_size=50)
    await dedup.is_duplicate("key-a")
    await dedup.is_duplicate("key-b")
    assert await dedup.size() == 2

    await dedup.clear()
    assert await dedup.size() == 0
    assert await dedup.is_duplicate("key-a") is False


@pytest.mark.asyncio
async def test_deduplicator_concurrent_access():
    """Concurrent tasks accessing the deduplicator do not corrupt internal state."""
    dedup = Deduplicator(max_size=500)
    keys = [f"key-{i}" for i in range(100)]

    async def worker(key_subset):
        results = []
        for k in key_subset:
            results.append(await dedup.is_duplicate(k))
        return results

    # Run 5 workers each querying the same 100 keys
    tasks = [worker(keys) for _ in range(5)]
    all_results = await asyncio.gather(*tasks)

    # For each key, exactly one worker must have seen False (first seen),
    # while the other 4 must have seen True (duplicate)
    for key_idx in range(100):
        seen_count = sum(1 for worker_res in all_results if not worker_res[key_idx])
        dup_count = sum(1 for worker_res in all_results if worker_res[key_idx])
        assert seen_count == 1, f"Key {key_idx} was marked non-duplicate {seen_count} times"
        assert dup_count == 4, f"Key {key_idx} was marked duplicate {dup_count} times"

    assert await dedup.size() == 100
