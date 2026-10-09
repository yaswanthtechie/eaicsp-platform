"""
Regression tests for PR feedback item 7: Raw JSON Body Forwarding.

Proves:
1. Exact request body bytes are forwarded without modification.
2. Duplicate JSON keys are preserved (not dropped or deduplicated).
3. Arbitrary-precision decimal representations are preserved verbatim.
4. Unicode byte sequences remain bit-for-bit identical.
5. HMAC signatures computed over the raw body match downstream.
"""

import hmac
import hashlib
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.ratelimit import limiter
from app.services.circuit_breaker import circuit_breaker_manager
from app.services.metrics import metrics_collector


@pytest.fixture(autouse=True)
def reset_state():
    circuit_breaker_manager.reset()
    metrics_collector.reset()
    limiter.enabled = False
    yield
    circuit_breaker_manager.reset()
    metrics_collector.reset()
    limiter.enabled = True


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_exact_raw_body_bytes_forwarded(mock_send, client):
    """Raw request bytes must pass through to downstream without rewrite."""
    mock_send.return_value = httpx.Response(
        status_code=201,
        content=b'{"created": true}',
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "http://test"),
    )
    raw_payload = b'{"name":   "custom-spacing"  ,   "count": 42}'
    response = client.post(
        "/api/v1/inventory",
        content=raw_payload,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 201
    mock_send.assert_called_once()
    called_request = mock_send.call_args[0][0]
    assert called_request.content == raw_payload


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_duplicate_keys_preserved(mock_send, client):
    """Duplicate JSON keys must NOT be removed by JSON re-serialization."""
    mock_send.return_value = httpx.Response(
        status_code=201,
        content=b'{"ok": true}',
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "http://test"),
    )
    duplicate_key_body = b'{"sku": "SKU-A", "sku": "SKU-B"}'
    response = client.post(
        "/api/v1/inventory",
        content=duplicate_key_body,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 201
    called_request = mock_send.call_args[0][0]
    assert called_request.content == duplicate_key_body


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_decimal_precision_preserved(mock_send, client):
    """Extreme decimal precision must not be rounded by standard float serialization."""
    mock_send.return_value = httpx.Response(
        status_code=201,
        content=b'{"ok": true}',
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "http://test"),
    )
    high_precision_body = b'{"amount": 1234567890.123456789012345678901234567890}'
    response = client.post(
        "/api/v1/inventory",
        content=high_precision_body,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 201
    called_request = mock_send.call_args[0][0]
    assert called_request.content == high_precision_body


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_unicode_bytes_preserved(mock_send, client):
    """Unicode sequences (Japanese characters, emoji) must remain unchanged."""
    mock_send.return_value = httpx.Response(
        status_code=201,
        content=b'{"ok": true}',
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "http://test"),
    )
    unicode_body = '{"greeting": "こんにちは世界", "icon": "🚀"}'.encode("utf-8")
    response = client.post(
        "/api/v1/inventory",
        content=unicode_body,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    assert response.status_code == 201
    called_request = mock_send.call_args[0][0]
    assert called_request.content == unicode_body


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_hmac_signature_compatibility(mock_send, client):
    """HMAC signature calculated by caller must remain valid downstream."""
    mock_send.return_value = httpx.Response(
        status_code=201,
        content=b'{"verified": true}',
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "http://test"),
    )
    secret = b"shared-webhook-secret"
    body = b'{"event": "item.created", "item_id": 999, "nested": {"a": 1}}'
    expected_signature = hmac.new(secret, body, hashlib.sha256).hexdigest()

    response = client.post(
        "/api/v1/inventory",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature-SHA256": expected_signature,
        },
    )
    assert response.status_code == 201
    called_request = mock_send.call_args[0][0]
    # Downstream verifies signature against received bytes
    received_signature = hmac.new(secret, called_request.content, hashlib.sha256).hexdigest()
    assert received_signature == expected_signature
