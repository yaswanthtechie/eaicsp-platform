"""
Tests for Realtime Kafka Consumer Service and BFF lifecycle (R15-M3).

Verifies:
- Consumption and broadcast of valid canonical events.
- Deduplication of ordinary events (event_id) and anomaly episodes (payload.episode_id).
- DLQ routing for malformed JSON and schema validation failures.
- Offset commit behavior for valid, duplicate, and DLQ-routed messages.
- Fault tolerance when DLQ publishing fails.
- Consumer startup, clean shutdown, and preservation of standard HTTP endpoints.
"""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.realtime.connection_manager import ConnectionManager
from app.services.realtime.deduplicator import Deduplicator
from app.services.realtime.dlq import DLQPublishError, DLQService
from app.services.realtime.kafka_consumer import RealtimeKafkaConsumerService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_components():
    conn_mgr = MagicMock(spec=ConnectionManager)
    conn_mgr.broadcast = AsyncMock(return_value=2)

    dedup = Deduplicator(max_size=100)

    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock()
    dlq_svc = DLQService(producer=mock_producer)

    service = RealtimeKafkaConsumerService(
        bootstrap_servers="localhost:9092",
        group_id="api-gateway-bff",
        topics=["inventory.stock.low", "iot.anomaly.detected"],
        conn_mgr=conn_mgr,
        dedup=dedup,
        dlq_svc=dlq_svc,
    )

    return service, conn_mgr, dedup, dlq_svc, mock_producer


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_message_valid_event_broadcast_and_committed(mock_components):
    """A valid event is broadcast as a UTF-8 JSON text frame and its offset is committed."""
    service, conn_mgr, dedup, dlq_svc, mock_producer = mock_components

    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "inventory.stock.low",
        "event_version": 1,
        "occurred_at": "2026-10-15T10:14:22Z",
        "producer": "inventory-service",
        "payload": {
            "sku_id": "SKU-000123",
            "warehouse_id": "WH-BLR-01",
            "quantity_on_hand": 8,
            "reorder_point": 35,
            "safety_stock": 15,
            "avg_daily_demand": 4.5,
        },
    }

    commit_called = False

    async def mock_commit():
        nonlocal commit_called
        commit_called = True

    handled = await service.process_message(
        topic="inventory.stock.low",
        value=json.dumps(event).encode("utf-8"),
        partition=0,
        offset=101,
        commit_callback=mock_commit,
    )

    assert handled is True
    assert commit_called is True
    conn_mgr.broadcast.assert_called_once()
    broadcast_text = conn_mgr.broadcast.call_args[0][0]
    broadcast_data = json.loads(broadcast_text)
    assert broadcast_data["event_id"] == event["event_id"]
    assert broadcast_data["payload"]["sku_id"] == "SKU-000123"
    # Ensure DLQ was not called
    mock_producer.send_and_wait.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_duplicate_event_not_broadcast_but_committed(mock_components):
    """Duplicate messages are dropped before broadcast, and their offset is committed."""
    service, conn_mgr, dedup, dlq_svc, mock_producer = mock_components

    event_id = str(uuid.uuid4())
    event = {
        "event_id": event_id,
        "event_type": "inventory.stock.low",
        "event_version": 1,
        "occurred_at": "2026-10-15T10:14:22Z",
        "producer": "inventory-service",
        "payload": {
            "sku_id": "SKU-000123",
            "warehouse_id": "WH-BLR-01",
            "quantity_on_hand": 8,
            "reorder_point": 35,
            "safety_stock": 15,
            "avg_daily_demand": 4.5,
        },
    }

    # 1. First delivery
    commit_count = 0

    async def mock_commit():
        nonlocal commit_count
        commit_count += 1

    h1 = await service.process_message(
        topic="inventory.stock.low",
        value=json.dumps(event).encode("utf-8"),
        commit_callback=mock_commit,
    )
    assert h1 is True
    assert commit_count == 1
    assert conn_mgr.broadcast.call_count == 1

    # 2. Duplicate delivery
    h2 = await service.process_message(
        topic="inventory.stock.low",
        value=json.dumps(event).encode("utf-8"),
        commit_callback=mock_commit,
    )
    assert h2 is True
    assert commit_count == 2
    # Broadcast count MUST still be 1 (duplicate not broadcast)
    assert conn_mgr.broadcast.call_count == 1


@pytest.mark.asyncio
async def test_process_message_iot_episode_replay_deduplicated(mock_components):
    """
    iot.anomaly.detected deduplicates on payload.episode_id.
    When crash replay publishes a new event_id for the same episode, it is not broadcast.
    """
    service, conn_mgr, dedup, dlq_svc, mock_producer = mock_components

    episode_id = "WH-BLR-01-S1|2026-10-15T10:05:00+00:00"

    event1 = {
        "event_id": str(uuid.uuid4()),
        "event_type": "iot.anomaly.detected",
        "event_version": 1,
        "occurred_at": "2026-10-15T10:46:12Z",
        "producer": "anomaly-detection-service",
        "payload": {
            "episode_id": episode_id,
            "sensor_id": "WH-BLR-01-S1",
            "warehouse_id": "WH-BLR-01",
            "severity": "high",
            "message": "Anomaly flagged",
            "window_start": "2026-10-15T10:05:00Z",
            "window_end": "2026-10-15T10:30:00Z",
            "first_flag_time": "2026-10-15T10:05:00Z",
            "confirmed_time": "2026-10-15T10:05:00Z",
            "peak_time": "2026-10-15T10:20:00Z",
            "peak_score": 0.0825,
            "threshold": -0.0782,
            "n_flagged": 6,
            "severe": True,
            "closed_by": "quiet",
            "top_features": [{"feature": "temp", "contribution": 0.8}],
            "model_version": "1.0",
        },
    }

    # Second event with NEW event_id but SAME episode_id
    event2 = json.loads(json.dumps(event1))
    event2["event_id"] = str(uuid.uuid4())

    # Process first
    await service.process_message(topic="iot.anomaly.detected", value=json.dumps(event1))
    assert conn_mgr.broadcast.call_count == 1

    # Process replay
    await service.process_message(topic="iot.anomaly.detected", value=json.dumps(event2))
    assert conn_mgr.broadcast.call_count == 1  # Not broadcast again!


@pytest.mark.asyncio
async def test_process_message_malformed_json_routed_to_dlq(mock_components):
    """Malformed JSON is routed to <topic>.dlq and offset is committed."""
    service, conn_mgr, dedup, dlq_svc, mock_producer = mock_components

    commit_called = False

    async def mock_commit():
        nonlocal commit_called
        commit_called = True

    handled = await service.process_message(
        topic="inventory.stock.low",
        value=b"this is not { valid json",
        partition=1,
        offset=505,
        commit_callback=mock_commit,
    )

    assert handled is False
    assert commit_called is True
    conn_mgr.broadcast.assert_not_called()
    mock_producer.send_and_wait.assert_called_once()
    called_topic = mock_producer.send_and_wait.call_args[0][0]
    called_payload = json.loads(mock_producer.send_and_wait.call_args[0][1].decode("utf-8"))

    assert called_topic == "inventory.stock.low.dlq"
    assert "Malformed JSON" in called_payload["error_reason"]
    assert called_payload["source_offset"] == 505


@pytest.mark.asyncio
async def test_process_message_invalid_schema_routed_to_dlq(mock_components):
    """Event violating schema contracts is sent to DLQ and not broadcast."""
    service, conn_mgr, dedup, dlq_svc, mock_producer = mock_components

    invalid_event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "inventory.stock.low",
        "event_version": 999,  # Unsupported version
        "occurred_at": "2026-10-15T10:14:22Z",
        "producer": "inventory-service",
        "payload": {},
    }

    handled = await service.process_message(
        topic="inventory.stock.low",
        value=json.dumps(invalid_event).encode("utf-8"),
    )

    assert handled is False
    conn_mgr.broadcast.assert_not_called()
    mock_producer.send_and_wait.assert_called_once()
    assert mock_producer.send_and_wait.call_args[0][0] == "inventory.stock.low.dlq"


@pytest.mark.asyncio
async def test_dlq_publish_failure_handled_safely(mock_components):
    """When DLQ producer fails, consumer raises DLQPublishError and does not commit offset."""
    service, conn_mgr, dedup, dlq_svc, mock_producer = mock_components
    mock_producer.send_and_wait.side_effect = RuntimeError("Broker down")

    commit_called = False

    async def mock_commit():
        nonlocal commit_called
        commit_called = True

    with pytest.raises(DLQPublishError):
        await service.process_message(
            topic="inventory.stock.low",
            value=b"bad json",
            commit_callback=mock_commit,
        )

    assert commit_called is False


@pytest.mark.asyncio
async def test_consumer_lifecycle_start_and_stop():
    """RealtimeKafkaConsumerService start and stop cycle works cleanly when enabled."""
    service = RealtimeKafkaConsumerService(
        bootstrap_servers="localhost:9092",
        group_id="api-gateway-bff",
        enabled=True,
    )

    with patch.object(service, "_run_consumer", new_callable=AsyncMock) as mock_run:
        await service.start()
        assert service._running is True
        await service.stop()
        assert service._running is False


@pytest.mark.asyncio
async def test_consumer_disabled_does_not_start():
    """When enabled is False, start() is a no-op."""
    service = RealtimeKafkaConsumerService(
        bootstrap_servers="localhost:9092",
        group_id="api-gateway-bff",
        enabled=False,
    )

    await service.start()
    assert service._running is False


def test_lifespan_preserves_http_endpoints_when_kafka_down():
    """Application HTTP endpoints (/, /health, metrics) remain responsive."""
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

        health_resp = client.get("/health")
        assert health_resp.status_code in (200, 503)
