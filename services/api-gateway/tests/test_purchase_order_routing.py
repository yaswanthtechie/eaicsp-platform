"""
Regression tests: /api/v1/purchase-orders belongs to supplier-portal (:8004).
The gateway must forward it unchanged and health-check it on its own.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.health import get_system_health


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_purchase_orders_forwarded_to_supplier_portal_unchanged(mock_send, client):
    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b"[]",
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://test"),
    )

    response = client.get("/api/v1/purchase-orders/PO-1?status=open")

    assert response.status_code == 200
    called_request = mock_send.call_args[0][0]
    assert str(called_request.url) == "http://localhost:8004/api/v1/purchase-orders/PO-1?status=open"


@patch("app.services.health._ping_service", new_callable=AsyncMock)
def test_health_pings_supplier_portal(mock_ping):
    mock_ping.side_effect = lambda c, name, url: (name, "UP")
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(http_client=object())))

    asyncio.run(get_system_health(request))

    pinged_urls = [call.args[2] for call in mock_ping.call_args_list]
    assert "http://localhost:8004" in pinged_urls
