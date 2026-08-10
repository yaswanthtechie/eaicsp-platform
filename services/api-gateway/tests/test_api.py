import httpx
import pytest
from unittest.mock import AsyncMock, patch
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
    mock_get.side_effect = Exception("Failed to connect")

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["inventory"] == "DOWN"
    assert data["auth"] == "DOWN"


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_reverse_proxy_success(mock_send, client):
    """
    Successful reverse proxy request.
    """
    mock_send.return_value = httpx.Response(
        status_code=200,
        json={"data": "success"},
        request=httpx.Request("GET", "http://test"),
    )

    response = client.get("/api/v1/inventory/items")

    assert response.status_code == 200
    assert response.json() == {
        "data": "success"
    }


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