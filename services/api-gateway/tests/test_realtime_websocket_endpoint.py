"""
Tests for Realtime KPI WebSocket Endpoint (R15-M3).

Path: WS /api/v1/analytics/kpis/real-time

Verifies:
- Successful connection handshake with query param token and subprotocol header.
- Heartbeat ping/pong messages.
- Authentication close codes (4401, 4403, 1013).
- Connection manager registration and broadcast to multiple simultaneous clients.
- Clean eviction of failed or disconnected clients without disrupting other clients.
"""

import asyncio
import copy
import json
import uuid
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from app.main import app
from app.services.realtime.connection_manager import connection_manager
from app.services.realtime.deduplicator import Deduplicator
from app.services.realtime.dlq import DLQService
from app.services.realtime.kafka_consumer import RealtimeKafkaConsumerService
from tests.test_realtime_events_validation import (
    ALL_SAMPLES,
    IOT_ANOMALY_DETECTED_SAMPLE,
)


def assert_accepted_then_closed(client, url, expected_code):
    """
    Verify that the WebSocket handshake is accepted
    before the connection is closed with the expected code.
    """
    with client.websocket_connect(url) as ws:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_text()

    assert exc_info.value.code == expected_code


def _fresh_consumer():
    """A consumer wired to the real connection manager with its own dedup cache."""
    return RealtimeKafkaConsumerService(
        conn_mgr=connection_manager,
        dedup=Deduplicator(max_size=100),
        dlq_svc=DLQService(producer=AsyncMock()),
        enabled=False,
    )


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_websocket_connect_success_with_query_token(mock_post, client):
    """Client with valid token in query param connects successfully."""
    mock_post.return_value = httpx.Response(
        200,
        json={"valid": True, "role": "analyst", "is_active": True, "email": "analyst@test.com"},
    )

    with client.websocket_connect("/api/v1/analytics/kpis/real-time?token=valid-jwt") as websocket:
        # Send heartbeat ping
        websocket.send_text(json.dumps({"type": "ping"}))
        response_text = websocket.receive_text()
        pong = json.loads(response_text)
        assert pong["type"] == "pong"
        assert "timestamp" in pong


@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_websocket_connect_success_with_subprotocol(mock_post, client):
    """Client using Sec-WebSocket-Protocol: bearer, <token> connects successfully."""
    mock_post.return_value = httpx.Response(
        200,
        json={"valid": True, "role": "ceo", "is_active": True},
    )

    with client.websocket_connect(
        "/api/v1/analytics/kpis/real-time",
        subprotocols=["bearer", "valid-subproto-jwt"],
    ) as websocket:
        assert websocket.accepted_subprotocol == "bearer"
        websocket.send_text(json.dumps({"type": "ping"}))
        pong = json.loads(websocket.receive_text())
        assert pong["type"] == "pong"


def test_websocket_missing_token_closed_4401(client):
    """Connection without token is rejected with close code 4401."""
    assert_accepted_then_closed(
        client,
        "/api/v1/analytics/kpis/real-time",
        4401,
    )


@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_websocket_invalid_token_closed_4401(mock_post, client):
    """Connection with invalid/expired token is rejected with 4401."""
    mock_post.return_value = httpx.Response(401, json={"detail": "Token expired"})

    assert_accepted_then_closed(
        client,
        "/api/v1/analytics/kpis/real-time?token=expired",
        4401,
    )


@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_websocket_unauthorized_role_closed_4403(mock_post, client):
    """Authenticated user with disallowed role (e.g. supplier) is rejected with 4403."""
    mock_post.return_value = httpx.Response(
        200,
        json={"valid": True, "role": "supplier", "is_active": True},
    )

    assert_accepted_then_closed(
        client,
        "/api/v1/analytics/kpis/real-time?token=supplier-token",
        4403,
    )


@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_websocket_platform_unavailable_closed_1013(mock_post, client):
    """When Platform service is unavailable, handshake is closed with 1013."""
    mock_post.side_effect = httpx.ConnectError("Platform service down")

    assert_accepted_then_closed(
        client,
        "/api/v1/analytics/kpis/real-time?token=any-token",
        1013,
    )


@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_broadcast_to_multiple_simultaneous_clients(mock_post, client):
    """Broadcasting a message delivers UTF-8 JSON frame to all connected clients."""
    mock_post.return_value = httpx.Response(
        200,
        json={"valid": True, "role": "warehouse_manager", "is_active": True},
    )

    with client.websocket_connect("/api/v1/analytics/kpis/real-time?token=tok-1") as ws1:
        with client.websocket_connect("/api/v1/analytics/kpis/real-time?token=tok-2") as ws2:
            test_event = {
                "event_id": "test-broadcast-1",
                "event_type": "inventory.stock.low",
                "payload": {"sku_id": "SKU-0001"},
            }

            import asyncio
            # Broadcast to both
            asyncio.run(connection_manager.broadcast(json.dumps(test_event)))

            msg1 = json.loads(ws1.receive_text())
            msg2 = json.loads(ws2.receive_text())

            assert msg1["event_id"] == "test-broadcast-1"
            assert msg2["event_id"] == "test-broadcast-1"


@pytest.mark.asyncio
async def test_connection_manager_failed_send_eviction():
    """Connection manager evicts failing connections without raising exceptions."""
    broken_ws = AsyncMock()
    broken_ws.send_text.side_effect = RuntimeError("Broken pipe")

    healthy_ws = AsyncMock()
    healthy_ws.send_text.return_value = None

    cm = connection_manager.__class__()
    await cm.connect(broken_ws)
    await cm.connect(healthy_ws)
    assert await cm.count() == 2

    sent_count = await cm.broadcast('{"hello": "world"}')
    assert sent_count == 1
    assert await cm.count() == 1  # broken_ws was evicted


@pytest.mark.parametrize(
    "example",
    ALL_SAMPLES,
    ids=[sample["event_type"] for sample in ALL_SAMPLES],
)
@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_contract_examples_reach_connected_websocket_clients(mock_post, client, example):
    """Every contract example event processed by the consumer reaches a connected client."""
    mock_post.return_value = httpx.Response(
        200,
        json={"valid": True, "role": "analyst", "is_active": True},
    )

    consumer = _fresh_consumer()

    with client.websocket_connect("/api/v1/analytics/kpis/real-time?token=valid-jwt") as ws:
        handled = asyncio.run(
            consumer.process_message(
                topic=example["event_type"],
                value=json.dumps(example),
            )
        )
        assert handled is True
        assert json.loads(ws.receive_text()) == example


@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_replayed_iot_anomaly_episode_delivered_once(mock_post, client):
    """A replayed IoT anomaly with same episode_id but different event_id is delivered only once."""
    mock_post.return_value = httpx.Response(
        200,
        json={"valid": True, "role": "analyst", "is_active": True},
    )

    consumer = _fresh_consumer()

    first = copy.deepcopy(IOT_ANOMALY_DETECTED_SAMPLE)
    replay = copy.deepcopy(IOT_ANOMALY_DETECTED_SAMPLE)
    replay["event_id"] = str(uuid.uuid4())
    # Keep the same episode_id
    assert replay["payload"]["episode_id"] == first["payload"]["episode_id"]

    marker = {
        "event_id": str(uuid.uuid4()),
        "event_type": "marker.event",
        "payload": {"marker": True},
    }

    with client.websocket_connect("/api/v1/analytics/kpis/real-time?token=valid-jwt") as ws:
        async def run_scenario():
            h1 = await consumer.process_message(
                topic=first["event_type"],
                value=json.dumps(first),
            )
            h2 = await consumer.process_message(
                topic=replay["event_type"],
                value=json.dumps(replay),
            )
            await connection_manager.broadcast(json.dumps(marker))
            return h1, h2

        h1, h2 = asyncio.run(run_scenario())
        assert h1 is True
        assert h2 is True

        # Assert the first WebSocket frame contains the original event ID
        msg1 = json.loads(ws.receive_text())
        assert msg1["event_id"] == first["event_id"]

        # Assert the next frame is the marker, proving the replay was not broadcast
        msg2 = json.loads(ws.receive_text())
        assert msg2["event_id"] == marker["event_id"]
        assert msg2["event_type"] == "marker.event"
