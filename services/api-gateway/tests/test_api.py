import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
import httpx

from app.main import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the API Gateway", "docs_url": "/docs"}

def test_invalid_service():
    response = client.get("/invalid-path")
    assert response.status_code == 404
    assert "Service not found" in response.json()["detail"]

@patch("app.services.health.httpx.AsyncClient.get", new_callable=AsyncMock)
def test_health_endpoint_all_up(mock_get):
    # Mock all downstreams as UP (HTTP 200)
    mock_response = httpx.Response(200, request=httpx.Request("GET", "http://test"))
    mock_get.return_value = mock_response

    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "inventory" in data
    assert data["inventory"] == "UP"
    assert "auth" in data
    assert data["auth"] == "UP"

@patch("app.services.health.httpx.AsyncClient.get", new_callable=AsyncMock)
def test_health_endpoint_service_down(mock_get):
    # Mock connection error to simulate DOWN
    mock_get.side_effect = httpx.RequestError("Failed to connect")

    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "inventory" in data
    assert data["inventory"] == "DOWN"
    assert data["auth"] == "DOWN"

@patch("app.services.proxy.execute_proxy_request", new_callable=AsyncMock)
def test_reverse_proxy_success(mock_execute):
    # Mock a successful downstream response
    mock_response = httpx.Response(
        200, 
        json={"data": "success"}, 
        request=httpx.Request("GET", "http://test")
    )
    mock_execute.return_value = mock_response

    response = client.get("/api/v1/inventory/items")
    assert response.status_code == 200
    assert response.json() == {"data": "success"}

@patch("app.services.proxy.execute_proxy_request", new_callable=AsyncMock)
def test_reverse_proxy_service_unavailable(mock_execute):
    # Mock a network request error triggering the 503 fallback
    mock_execute.side_effect = httpx.RequestError("Connection Refused")

    response = client.get("/api/v1/inventory/items")
    assert response.status_code == 503
    assert response.json() == {"error": "Inventory service unavailable"}

@patch("app.services.proxy.execute_proxy_request", new_callable=AsyncMock)
def test_reverse_proxy_timeout(mock_execute):
    # Mock a timeout triggering the 504 fallback
    mock_execute.side_effect = httpx.TimeoutException("Read Timeout")

    response = client.get("/api/v1/inventory/items")
    assert response.status_code == 504
    assert response.json() == {"error": "Inventory service timeout"}
