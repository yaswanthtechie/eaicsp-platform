"""
Tests for API Version 2 stub endpoints and versioning isolation.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


def test_v2_inventory_items_stub(client):
    """
    Test GET /api/v2/inventory/items returns 200 with breaking envelope schema.
    """
    response = client.get("/api/v2/inventory/items")
    assert response.status_code == 200

    data = response.json()
    assert data["version"] == "v2"
    assert "data" in data
    assert isinstance(data["data"], list)
    assert "meta" in data
    assert isinstance(data["meta"], dict)


def test_v2_status_endpoint(client):
    """
    Test GET /api/v2/status returns 200 with v2 active status.
    """
    response = client.get("/api/v2/status")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "active"
    assert data["version"] == "v2.0.0-stub"


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_v1_inventory_unaffected(mock_send, client):
    """
    Test that GET /api/v1/inventory/items still follows the existing v1 proxy logic.
    """
    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"source": "v1_inventory"}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://localhost:8001/api/v1/inventory/items"),
    )

    response = client.get("/api/v1/inventory/items")
    assert response.status_code == 200
    assert response.json() == {"source": "v1_inventory"}


def test_v2_unmapped_path_returns_404(client):
    """
    Test that unmapped paths under /api/v2 fall through to standard 404 behavior.
    """
    response = client.get("/api/v2/unmapped")
    assert response.status_code == 404
    assert "Service not found" in response.json()["detail"]


def test_v2_middleware_integration(client):
    """
    Test that /api/v2 endpoints pass through global middleware (e.g. RequestIDMiddleware).
    """
    response = client.get("/api/v2/status")
    assert response.status_code == 200
    assert "x-request-id" in response.headers


def test_v2_openapi_schema(client):
    """
    Test that /api/v2 endpoints appear in the generated OpenAPI schema.
    """
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200

    schema = response.json()
    assert "/api/v2/status" in schema["paths"]
    assert "/api/v2/inventory/items" in schema["paths"]
