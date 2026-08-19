import asyncio
import threading
import time

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app as gateway_app

# ----------------------------------------------------
# Dummy Inventory Service
# ----------------------------------------------------

dummy_inventory = FastAPI()


@dummy_inventory.get("/api/v1/inventory/items")
async def get_items():
    return {"source": "inventory"}


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


# ----------------------------------------------------
# Test Fixture
# ----------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def setup_dummy_services():
    """
    Start dummy downstream services.
    """

    inventory_server = UvicornTestServer(
        config=uvicorn.Config(
            dummy_inventory,
            host="127.0.0.1",
            port=8001,
            log_level="critical",
        )
    )

    shipments_server = UvicornTestServer(
        config=uvicorn.Config(
            dummy_shipments,
            host="127.0.0.1",
            port=8002,
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

    yield

    inventory_server.should_exit = True
    shipments_server.should_exit = True

    inventory_thread.join(timeout=2)
    shipments_thread.join(timeout=2)


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