from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """
    Create a FastAPI test client.
    """
    with TestClient(app) as test_client:
        yield test_client


def test_root_endpoint(client):
    """
    Test the root endpoint.
    """
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "API Gateway is running",
        "status": "healthy",
        "version": "1.0.0",
    }


def test_openapi_schema(client):
    """
    Test that the OpenAPI schema endpoint returns 200 and valid paths.
    """
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "/{path}" in schema["paths"]


def test_invalid_service(client):
    """
    Test invalid route.
    """
    response = client.get("/invalid-path")

    assert response.status_code == 404
    assert "Service not found" in response.json()["detail"]


@patch("httpx.AsyncClient.get", new_callable=AsyncMock)
def test_health_endpoint_all_up(mock_get, client):
    """
    All downstream services are healthy.
    """
    mock_get.return_value = httpx.Response(
        status_code=200,
        request=httpx.Request("GET", "http://test"),
    )

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["inventory"] == "UP"
    assert data["auth"] == "UP"


@patch("httpx.AsyncClient.get", new_callable=AsyncMock)
def test_health_endpoint_service_down(mock_get, client):
    """
    Downstream services are unavailable.
    """
    mock_get.side_effect = httpx.ConnectError(
        "Failed to connect",
        request=httpx.Request("GET", "http://test"),
    )

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["inventory"] == "DOWN"
    assert data["auth"] == "DOWN"


@pytest.mark.parametrize(
    "status_code,expected_status",
    [
        (200, "UP"),
        (201, "UP"),
        (204, "UP"),
        (400, "DOWN"),
        (401, "DOWN"),
        (403, "DOWN"),
        (404, "DOWN"),
        (500, "DOWN"),
        (502, "DOWN"),
        (503, "DOWN"),
        (504, "DOWN"),
    ],
)
@patch("httpx.AsyncClient.get", new_callable=AsyncMock)
def test_health_endpoint_status_code_boundaries(mock_get, client, status_code, expected_status):
    """
    Verify health check boundary: only 2xx responses are UP; 4xx and 5xx are DOWN.
    """
    mock_get.return_value = httpx.Response(
        status_code=status_code,
        request=httpx.Request("GET", "http://test"),
    )

    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    for svc_status in data.values():
        assert svc_status == expected_status


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_reverse_proxy_success(mock_send, client):
    # build a response with bytes content and content-type header
    content_bytes = b'{"data":"success"}'
    mock_send.return_value = httpx.Response(
        status_code=200,
        content=content_bytes,
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://test"),
    )

    response = client.get("/api/v1/inventory/items")

    assert response.status_code == 200
    assert response.json() == {"data": "success"}


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_reverse_proxy_service_unavailable(mock_send, client):
    """
    Downstream service unavailable.
    """
    mock_send.side_effect = httpx.ConnectError(
        "Connection Refused",
        request=httpx.Request("GET", "http://test"),
    )

    response = client.get("/api/v1/inventory/items")

    assert response.status_code == 503
    assert response.json() == {
        "error": "Inventory service unavailable"
    }


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_reverse_proxy_timeout(mock_send, client):
    """
    Downstream timeout.
    """
    mock_send.side_effect = httpx.TimeoutException(
        "Read Timeout",
        request=httpx.Request("GET", "http://test"),
    )

    response = client.get("/api/v1/inventory/items")

    assert response.status_code == 504
    assert response.json() == {
        "error": "Inventory service timeout"
    }


def test_request_id_header_injection_prevention(client):
    """
    Security: Verify that CR/LF characters in a client-supplied X-Request-ID
    header are stripped to prevent log injection and HTTP header injection attacks.
    The response must echo the sanitized value (without newlines).
    """
    malicious_id = "legit-id\r\nX-Injected: evil"
    response = client.get("/", headers={"x-request-id": malicious_id})

    assert response.status_code == 200
    returned_id = response.headers.get("x-request-id", "")
    # CR and LF must NOT appear in the echoed header
    assert "\r" not in returned_id
    assert "\n" not in returned_id
    # The sanitized prefix should still appear
    assert "legit-id" in returned_id


def test_request_id_generated_when_injection_only(client):
    """
    Security: Verify that if a client-supplied X-Request-ID contains ONLY
    newline characters, after stripping it becomes empty, and a fresh UUID
    is generated instead of propagating an empty value.
    """
    response = client.get("/", headers={"x-request-id": "\r\n"})

    assert response.status_code == 200
    returned_id = response.headers.get("x-request-id", "")
    # Must be a non-empty, sanitized request ID (the UUID fallback)
    assert len(returned_id) > 0
    assert "\r" not in returned_id
    assert "\n" not in returned_id


@patch("httpx.AsyncClient.get", new_callable=AsyncMock)
def test_health_endpoint_unexpected_exception(mock_get, client):
    """
    Bug fix: Verify the health endpoint returns 200 with DOWN status for any
    unexpected exception during a downstream health check call. The broad
    `except Exception` in _ping_service ensures the gateway never crashes.
    """
    mock_get.side_effect = RuntimeError("unexpected internal failure")

    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    # All services should show DOWN, not crash the gateway
    for status in data.values():
        assert status == "DOWN"