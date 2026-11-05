"""
Tests for Gateway BFF Service-to-Service API Key Authentication (Round 15 Milestone 5).

Verifies:
1. Configured Gateway BFF API key (GATEWAY_BFF_SERVICE_API_KEY) is sent on outbound
   calls to downstream services with the exact header name 'X-API-Key'.
2. Backward-compatible alias API_GATEWAY_SERVICE_API_KEY works identically.
3. Client-forged X-API-Key or x-api-key headers cannot override the Gateway's configured key.
4. Client-forged X-API-Key headers are stripped even when no Gateway key is configured.
5. No secret keys are leaked into logs, error messages, or response bodies.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.log_redaction import redact_token_query
from app.main import app
from app.middleware.rate_limit import in_memory_limiter
from app.middleware.ratelimit import limiter
from app.services.circuit_breaker import circuit_breaker_manager
from app.services.metrics import metrics_collector


@pytest.fixture(autouse=True)
def reset_gateway_state():
    """Reset circuit breaker, metrics, rate limiters, and service key settings."""
    orig_canonical = settings.GATEWAY_BFF_SERVICE_API_KEY
    orig_legacy = settings.API_GATEWAY_SERVICE_API_KEY
    circuit_breaker_manager.reset()
    metrics_collector.reset()
    in_memory_limiter.reset()
    limiter.enabled = False
    yield
    settings.GATEWAY_BFF_SERVICE_API_KEY = orig_canonical
    settings.API_GATEWAY_SERVICE_API_KEY = orig_legacy
    circuit_breaker_manager.reset()
    metrics_collector.reset()
    in_memory_limiter.reset()
    limiter.enabled = True


@pytest.fixture
def client():
    """Create a FastAPI test client for the gateway."""
    with TestClient(app) as test_client:
        yield test_client


# ===========================================================================
# 1. Configured Gateway API Key on Outbound Requests
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_configured_gateway_api_key_sent_on_outbound_http_calls(mock_send, client):
    """
    Verify that when GATEWAY_BFF_SERVICE_API_KEY is configured,
    the exact header 'X-API-Key' is present with the secret value on outbound requests.
    """
    test_key = "sk_gateway_bff_live_secret_12345"
    settings.GATEWAY_BFF_SERVICE_API_KEY = test_key
    settings.API_GATEWAY_SERVICE_API_KEY = test_key

    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"items": []}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://localhost:8001/api/v1/inventory/items"),
    )

    response = client.get("/api/v1/inventory/items")
    assert response.status_code == 200
    mock_send.assert_called_once()

    downstream_req: httpx.Request = mock_send.call_args[0][0]
    # Header must be present
    assert "x-api-key" in downstream_req.headers
    assert downstream_req.headers["x-api-key"] == test_key

    # Exact casing verification in downstream raw headers
    raw_header_names = [k.decode("latin1") for k, _ in downstream_req.headers.raw]
    assert "X-API-Key" in raw_header_names


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_legacy_api_gateway_service_api_key_fallback(mock_send, client):
    """
    Verify backward compatibility: if only API_GATEWAY_SERVICE_API_KEY is configured,
    it is forwarded as 'X-API-Key'.
    """
    legacy_key = "sk_legacy_api_gateway_secret_99999"
    settings.GATEWAY_BFF_SERVICE_API_KEY = None
    settings.API_GATEWAY_SERVICE_API_KEY = legacy_key

    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"items": []}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://localhost:8001/api/v1/inventory/items"),
    )

    response = client.get("/api/v1/inventory/items")
    assert response.status_code == 200
    mock_send.assert_called_once()

    downstream_req: httpx.Request = mock_send.call_args[0][0]
    assert downstream_req.headers["x-api-key"] == legacy_key
    raw_header_names = [k.decode("latin1") for k, _ in downstream_req.headers.raw]
    assert "X-API-Key" in raw_header_names


# ===========================================================================
# 2. Client-Forged Headers Cannot Override Configured Gateway Key
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_client_forged_api_key_cannot_override_configured_key(mock_send, client):
    """
    Verify that an untrusted caller cannot forge or override the Gateway's
    configured service API key.
    """
    genuine_key = "sk_genuine_gateway_bff_secret_555"
    settings.GATEWAY_BFF_SERVICE_API_KEY = genuine_key
    settings.API_GATEWAY_SERVICE_API_KEY = genuine_key

    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"status": "ok"}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://localhost:8001/api/v1/inventory/items"),
    )

    # Client attempts to send forged keys under multiple casings
    response = client.get(
        "/api/v1/inventory/items",
        headers={
            "X-API-Key": "evil-forged-key-111",
            "x-api-key": "evil-forged-key-222",
        },
    )
    assert response.status_code == 200

    downstream_req: httpx.Request = mock_send.call_args[0][0]
    assert downstream_req.headers["x-api-key"] == genuine_key
    assert "evil-forged-key" not in str(downstream_req.headers)


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_client_forged_api_key_stripped_when_gateway_key_unconfigured(mock_send, client):
    """
    Verify that if the Gateway has no service key configured, client-supplied
    X-API-Key headers are still stripped and never forwarded downstream.
    """
    settings.GATEWAY_BFF_SERVICE_API_KEY = None
    settings.API_GATEWAY_SERVICE_API_KEY = None

    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"status": "ok"}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://localhost:8001/api/v1/inventory/items"),
    )

    response = client.get(
        "/api/v1/inventory/items",
        headers={"X-API-Key": "client-forged-untrusted-key"},
    )
    assert response.status_code == 200

    downstream_req: httpx.Request = mock_send.call_args[0][0]
    assert "x-api-key" not in downstream_req.headers
    assert "client-forged-untrusted-key" not in str(downstream_req.headers)


# ===========================================================================
# 3. No Secret Leaked Into Logs
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_api_key_never_leaked_into_logs(mock_send, client, caplog):
    """
    Verify that the Gateway service API key is never written to logs or access lines.
    """
    secret_key = "super_secret_gateway_key_do_not_log"
    settings.GATEWAY_BFF_SERVICE_API_KEY = secret_key
    settings.API_GATEWAY_SERVICE_API_KEY = secret_key

    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"status": "ok"}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://localhost:8001/api/v1/inventory/items"),
    )

    with caplog.at_level(logging.DEBUG):
        response = client.get("/api/v1/inventory/items")
        assert response.status_code == 200

    # Ensure the secret key string does not appear in any log output
    assert secret_key not in caplog.text


def test_log_redaction_redacts_api_key_query_and_headers():
    """Verify log redaction filters redact api_key and X-API-Key values."""
    query_line = "/api/v1/data?api_key=secret_12345&other=value"
    redacted = redact_token_query(query_line)
    assert "secret_12345" not in redacted
    assert "[REDACTED]" in redacted

    header_line = 'Outbound header: X-API-Key: "secret_api_key_value"'
    redacted_header = redact_token_query(header_line)
    assert "secret_api_key_value" not in redacted_header
    assert "[REDACTED]" in redacted_header
