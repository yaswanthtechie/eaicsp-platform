"""
Tests for Dead-Letter Queue (DLQ) routing (R15-M3).

Verifies:
- Standardized DLQ record generation with clear error reasons.
- Topic naming convention (<topic>.dlq).
- DLQ publish routing with mock producer.
- Safe failure handling: producer errors never crash the gateway.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.realtime.dlq import (
    DLQService,
    build_dlq_payload,
    resolve_dlq_topic,
)


def test_resolve_dlq_topic():
    """Verify topic resolution follows <topic>.dlq format."""
    assert resolve_dlq_topic("inventory.stock.low") == "inventory.stock.low.dlq"
    assert resolve_dlq_topic("iot.anomaly.detected") == "iot.anomaly.detected.dlq"
    assert resolve_dlq_topic("eta.shipment.predicted.dlq") == "eta.shipment.predicted.dlq"
    assert resolve_dlq_topic(None, "supplierrisk.score.changed") == "supplierrisk.score.changed.dlq"
    assert resolve_dlq_topic(None, None) == "api-gateway.dlq"


def test_build_dlq_payload_preserves_context():
    """build_dlq_payload packages original content, partition, offset, and error reason."""
    raw = {"bad": "event"}
    payload = build_dlq_payload(
        raw_message=raw,
        source_topic="inventory.stock.low",
        error_reason="Missing required envelope fields",
        partition=2,
        offset=1054,
    )
    assert payload["error_reason"] == "Missing required envelope fields"
    assert payload["source_topic"] == "inventory.stock.low"
    assert payload["source_partition"] == 2
    assert payload["source_offset"] == 1054
    assert payload["original_message"] == raw
    assert "failed_at" in payload


def test_build_dlq_payload_handles_bytes():
    """Bytes payload is safely decoded or stored."""
    raw = b"not json bytes"
    payload = build_dlq_payload(
        raw_message=raw,
        source_topic="forecast.batch.completed",
        error_reason="Malformed JSON",
    )
    assert payload["original_message"] == "not json bytes"


@pytest.mark.asyncio
async def test_dlq_service_route_success_with_async_producer():
    """DLQService successfully publishes to target topic using async producer."""
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock()

    dlq = DLQService(producer=mock_producer)
    success = await dlq.route(
        raw_message={"invalid": "payload"},
        source_topic="inventory.stock.low",
        error_reason="Validation failed",
        partition=0,
        offset=12,
    )

    assert success is True
    mock_producer.send_and_wait.assert_called_once()
    called_topic = mock_producer.send_and_wait.call_args[0][0]
    called_bytes = mock_producer.send_and_wait.call_args[0][1]

    assert called_topic == "inventory.stock.low.dlq"
    sent_dict = json.loads(called_bytes.decode("utf-8"))
    assert sent_dict["source_topic"] == "inventory.stock.low"
    assert sent_dict["error_reason"] == "Validation failed"


@pytest.mark.asyncio
async def test_dlq_service_route_with_no_producer_returns_false_safely():
    """If no producer is configured, DLQ returns False without crashing."""
    dlq = DLQService(producer=None)
    success = await dlq.route(
        raw_message="some message",
        source_topic="iot.anomaly.detected",
        error_reason="Unknown error",
    )
    assert success is False


@pytest.mark.asyncio
async def test_dlq_service_route_producer_failure_handled_safely():
    """If DLQ producer raises an error, route catches it and returns False."""
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock(side_effect=RuntimeError("Kafka broker error"))

    dlq = DLQService(producer=mock_producer)
    success = await dlq.route(
        raw_message="failing message",
        source_topic="data.pipeline.completed",
        error_reason="Failed",
    )
    assert success is False
