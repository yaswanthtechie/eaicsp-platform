import asyncio
import threading
import time

import pytest
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from app.main import app as gateway_app

# ----------------------------------------------------
# Dummy Inventory Service
# ----------------------------------------------------

dummy_inventory = FastAPI()


@dummy_inventory.get("/api/v1/inventory/items")
async def get_items():
    return {"source": "inventory"}


@dummy_inventory.get("/api/v1/inventory/secure-items")
async def get_secure_items(
    request: Request,
    response: Response,
):
    auth = request.headers.get("authorization")
    if not auth:
        response.status_code = 401
        response.headers["WWW-Authenticate"] = 'Bearer realm="inventory"'
        return {"detail": "Authentication required", "error": "MISSING_TOKEN"}
    if "invalid" in auth.lower():
        response.status_code = 401
        return {"detail": "Invalid token", "error": "INVALID_TOKEN"}
    if "forbidden" in auth.lower():
        response.status_code = 403
        return {"detail": "Forbidden resource", "error": "FORBIDDEN"}
    return {"source": "inventory", "received_auth": auth}


# ----------------------------------------------------
# Dummy Shipments Service
# ----------------------------------------------------

dummy_shipments = FastAPI()


@dummy_shipments.post("/api/v1/shipments")
async def create_shipment(payload: dict):
    return {
        "source": "shipments",
        "payload": payload,
    }


# ----------------------------------------------------
# Custom Uvicorn Server
# ----------------------------------------------------

class UvicornTestServer(uvicorn.Server):
    """
    Disable signal handlers for pytest.
    """

    def install_signal_handlers(self):
        pass


def run_server(server: uvicorn.Server):
    """
    Run a Uvicorn server in its own event loop.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(server.serve())
    finally:
        loop.close()


import socket

from app.core.config import settings
from app.middleware.rate_limit import in_memory_limiter
from app.middleware.ratelimit import limiter
from app.services.circuit_breaker import circuit_breaker_manager
from app.services.metrics import metrics_collector


def find_free_port() -> int:
    """Find an available ephemeral port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ----------------------------------------------------
# Test Fixture
# ----------------------------------------------------

@pytest.fixture(autouse=True)
def reset_test_state():
    """Reset rate limiter and circuit breaker state before and after each test."""
    in_memory_limiter.reset()
    circuit_breaker_manager.reset()
    metrics_collector.reset()
    limiter.enabled = False
    yield
    in_memory_limiter.reset()
    circuit_breaker_manager.reset()
    metrics_collector.reset()
    limiter.enabled = True


@pytest.fixture(scope="module", autouse=True)
def setup_dummy_services():
    """
    Start dummy downstream services on isolated ephemeral ports.
    """
    inv_port = find_free_port()
    ship_port = find_free_port()

    original_routes = dict(settings.SERVICE_ROUTES)
    settings.SERVICE_ROUTES["/api/v1/inventory"] = f"http://127.0.0.1:{inv_port}"
    settings.SERVICE_ROUTES["/api/v1/shipments"] = f"http://127.0.0.1:{ship_port}"

    inventory_server = UvicornTestServer(
        config=uvicorn.Config(
            dummy_inventory,
            host="127.0.0.1",
            port=inv_port,
            log_level="critical",
        )
    )

    shipments_server = UvicornTestServer(
        config=uvicorn.Config(
            dummy_shipments,
            host="127.0.0.1",
            port=ship_port,
            log_level="critical",
        )
    )

    inventory_thread = threading.Thread(
        target=run_server,
        args=(inventory_server,),
        daemon=True,
    )

    shipments_thread = threading.Thread(
        target=run_server,
        args=(shipments_server,),
        daemon=True,
    )

    inventory_thread.start()
    shipments_thread.start()

    # Give servers time to start
    time.sleep(1)

    try:
        yield
    finally:
        inventory_server.should_exit = True
        shipments_server.should_exit = True

        inventory_thread.join(timeout=2)
        shipments_thread.join(timeout=2)

        settings.SERVICE_ROUTES.clear()
        settings.SERVICE_ROUTES.update(original_routes)


# ----------------------------------------------------
# Integration Tests
# ----------------------------------------------------

def test_successful_routing_and_proxying():
    """
    Verify GET and POST requests are correctly
    proxied through the API Gateway.
    """

    with TestClient(gateway_app) as client:

        response = client.get("/api/v1/inventory/items")

        assert response.status_code == 200
        assert response.json() == {
            "source": "inventory"
        }

        response = client.post(
            "/api/v1/shipments",
            json={"id": 123},
        )

        assert response.status_code == 200

        assert response.json() == {
            "source": "shipments",
            "payload": {
                "id": 123
            },
        }


def test_503_fallback_unavailable_downstream():
    """
    Verify gateway returns 503 when
    downstream service is unavailable.
    """

    with TestClient(gateway_app) as client:

        response = client.get(
            "/api/v1/compliance/docs"
        )

        assert response.status_code == 503

        assert response.json() == {
            "error": "Compliance service unavailable"
        }


def test_round5_integration_auth_forwarding():
    """
    Round 5 Integration Test:
    Verify that an Authorization header sent by a client across the live HTTP
    socket is received verbatim by the downstream service.
    """
    token_str = "Bearer integration-test-token-val-987"
    with TestClient(gateway_app) as client:
        response = client.get(
            "/api/v1/inventory/secure-items",
            headers={"Authorization": token_str},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "inventory"
        assert data["received_auth"] == token_str


def test_round5_integration_downstream_401_passthrough():
    """
    Round 5 Integration Test:
    Verify that a genuine downstream 401 (e.g. missing or invalid token)
    passes through the Gateway to the caller with status 401, body intact,
    and WWW-Authenticate header preserved.
    """
    with TestClient(gateway_app) as client:
        # Case A: Missing token
        response_missing = client.get("/api/v1/inventory/secure-items")
        assert response_missing.status_code == 401
        assert response_missing.json() == {
            "detail": "Authentication required",
            "error": "MISSING_TOKEN",
        }
        assert response_missing.headers.get("www-authenticate") == 'Bearer realm="inventory"'

        # Case B: Invalid token
        response_invalid = client.get(
            "/api/v1/inventory/secure-items",
            headers={"Authorization": "Bearer invalid_secret_token"},
        )
        assert response_invalid.status_code == 401
        assert response_invalid.json() == {
            "detail": "Invalid token",
            "error": "INVALID_TOKEN",
        }


def test_round5_integration_downstream_403_passthrough():
    """
    Round 5 Integration Test:
    Verify that a downstream 403 Forbidden response passes through
    the Gateway unchanged without being swallowed or converted into 500.
    """
    with TestClient(gateway_app) as client:
        response = client.get(
            "/api/v1/inventory/secure-items",
            headers={"Authorization": "Bearer forbidden_role_token"},
        )
        assert response.status_code == 403
        assert response.json() == {
            "detail": "Forbidden resource",
            "error": "FORBIDDEN",
        }
