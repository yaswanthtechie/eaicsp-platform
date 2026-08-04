import asyncio
import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.main import app as gateway_app

dummy_inventory = FastAPI()
@dummy_inventory.get("/api/v1/inventory/items")
async def get_items():
    return {"source": "inventory"}

dummy_shipments = FastAPI()
@dummy_shipments.post("/api/v1/shipments")
async def create_shipment(payload: dict):
    return {"source": "shipments", "payload": payload}

class UvicornTestServer(uvicorn.Server):
    def install_signal_handlers(self):
        pass

@pytest.fixture(scope="module", autouse=True)
def setup_dummy_services():
    inventory_config = uvicorn.Config(dummy_inventory, host="127.0.0.1", port=8001, log_level="critical")
    shipments_config = uvicorn.Config(dummy_shipments, host="127.0.0.1", port=8002, log_level="critical")
    
    inventory_server = UvicornTestServer(config=inventory_config)
    shipments_server = UvicornTestServer(config=shipments_config)
    
    loop = asyncio.new_event_loop()
    
    # We run them in background threads since uvicorn doesn't play perfectly with the pytest-asyncio loop natively
    import threading
    def run_server(server, l):
        asyncio.set_event_loop(l)
        l.run_until_complete(server.serve())

    t1 = threading.Thread(target=run_server, args=(inventory_server, asyncio.new_event_loop()), daemon=True)
    t2 = threading.Thread(target=run_server, args=(shipments_server, asyncio.new_event_loop()), daemon=True)
    
    t1.start()
    t2.start()
    
    import time
    time.sleep(1) # wait for servers to start
    
    yield
    
    inventory_server.should_exit = True
    shipments_server.should_exit = True
    
    t1.join(timeout=2)
    t2.join(timeout=2)

def test_successful_routing_and_proxying():
    # Use TestClient to properly trigger the ASGI lifespan for gateway_app
    with TestClient(gateway_app) as client:
        # Test GET (idempotent, no body)
        response = client.get("/api/v1/inventory/items")
        assert response.status_code == 200
        assert response.json() == {"source": "inventory"}
        
        # Test POST (preserves body and proxies correctly)
        response = client.post("/api/v1/shipments", json={"id": 123})
        assert response.status_code == 200
        assert response.json() == {"source": "shipments", "payload": {"id": 123}}

def test_503_fallback_unavailable_downstream():
    with TestClient(gateway_app) as client:
        # Route to compliance service which is mocked in config to port 8003 but NOT running
        response = client.get("/api/v1/compliance/docs")
        assert response.status_code == 503
        assert response.json() == {"error": "Compliance service unavailable"}
