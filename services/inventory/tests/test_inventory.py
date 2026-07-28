from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.database import engine
from app.models.inventory import Base

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def create_item():
    payload = {
        "sku_id": "SKU100",
        "product_name": "Laptop",
        "warehouse_id": "WH001",
        "quantity_on_hand": 40,
        "avg_daily_demand": 5,
        "lead_time_days": 4,
        "safety_stock": 10,
    }

    response = client.post("/api/v1/inventory", json=payload)

    assert response.status_code == 201

    return response.json()


def test_create_inventory():

    payload = {
        "sku_id": "SKU101",
        "product_name": "Mouse",
        "warehouse_id": "WH001",
        "quantity_on_hand": 100,
        "avg_daily_demand": 5,
        "lead_time_days": 5,
        "safety_stock": 20,
    }

    response = client.post("/api/v1/inventory", json=payload)

    assert response.status_code == 201

    data = response.json()

    assert data["sku_id"] == "SKU101"
    assert data["product_name"] == "Mouse"
    assert data["warehouse_id"] == "WH001"
    assert data["reorder_point"] == 45


def test_get_inventory():

    create_item()

    response = client.get("/api/v1/inventory/SKU100")

    assert response.status_code == 200

    data = response.json()

    assert data["sku_id"] == "SKU100"
    assert data["product_name"] == "Laptop"
    assert data["reorder_point"] == 30


def test_low_stock():

    create_item()

    response = client.get("/api/v1/inventory/low-stock")

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)


def test_reorder_check():

    create_item()

    response = client.get(
        "/api/v1/inventory/SKU100/reorder-check"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["reorder_point"] == 30
    assert data["needs_reorder"] is False
    assert data["suggested_order_qty"] == 0


def test_simulate():

    create_item()

    response = client.post(
        "/api/v1/inventory/SKU100/simulate",
        json={
            "demand_spike_percent": 50
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert "current_quantity" in data
    assert "new_reorder_point" in data
    assert "needs_reorder" in data
    assert "suggested_order_qty" in data


def test_delete_inventory():

    create_item()

    response = client.delete("/api/v1/inventory/SKU100")

    assert response.status_code == 200

    assert response.json()["message"] == "Inventory deleted successfully"

    response = client.get("/api/v1/inventory/SKU100")

    assert response.status_code == 404


def test_reorder_above_point():

    payload = {
        "sku_id": "SKU102",
        "product_name": "Laptop",
        "warehouse_id": "WH1",
        "quantity_on_hand": 70,
        "safety_stock": 20,
        "lead_time_days": 3,
        "avg_daily_demand": 10,
    }

    client.post("/api/v1/inventory", json=payload)

    response = client.get("/api/v1/inventory/SKU102/reorder-check")

    data = response.json()

    assert data["reorder_point"] == 50
    assert data["needs_reorder"] is False


def test_reorder_below_point():

    payload = {
        "sku_id": "SKU103",
        "product_name": "Mouse",
        "warehouse_id": "WH1",
        "quantity_on_hand": 40,
        "safety_stock": 20,
        "lead_time_days": 3,
        "avg_daily_demand": 10,
    }

    client.post("/api/v1/inventory", json=payload)

    response = client.get("/api/v1/inventory/SKU103/reorder-check")

    data = response.json()

    assert data["reorder_point"] == 50
    assert data["needs_reorder"] is True


def test_reorder_equal_point():

    payload = {
        "sku_id": "SKU104",
        "product_name": "Keyboard",
        "warehouse_id": "WH1",
        "quantity_on_hand": 50,
        "safety_stock": 20,
        "lead_time_days": 3,
        "avg_daily_demand": 10,
    }

    client.post("/api/v1/inventory", json=payload)

    response = client.get("/api/v1/inventory/SKU104/reorder-check")

    data = response.json()

    assert data["reorder_point"] == 50
    assert data["needs_reorder"] is True


def test_duplicate_sku():

    payload = {
        "sku_id": "SKU200",
        "product_name": "Laptop",
        "warehouse_id": "WH001",
        "quantity_on_hand": 100,
        "avg_daily_demand": 10,
        "lead_time_days": 3,
        "safety_stock": 20,
    }

    response = client.post("/api/v1/inventory", json=payload)

    assert response.status_code == 201

    response = client.post("/api/v1/inventory", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "SKU already exists"


def test_suggested_order_quantity():

    payload = {
        "sku_id": "SKU201",
        "product_name": "Monitor",
        "warehouse_id": "WH001",
        "quantity_on_hand": 20,
        "avg_daily_demand": 10,
        "lead_time_days": 3,
        "safety_stock": 20,
    }

    client.post("/api/v1/inventory", json=payload)

    response = client.get("/api/v1/inventory/SKU201/reorder-check")

    assert response.status_code == 200

    data = response.json()

    assert data["reorder_point"] == 50
    assert data["suggested_order_qty"] == 30