from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def create_item():
    payload = {
        "sku_id": "SKU100",
        "product_name": "Laptop",
        "warehouse_id": "WH001",
        "quantity_on_hand": 40,
        "avg_daily_demand": 5,
        "lead_time_days": 4,
        "safety_stock": 10
    }

    response = client.post("/api/v1/inventory", json=payload)
    assert response.status_code ==200


def test_create_inventory():
    payload = {
        "sku_id": "SKU101",
        "product_name": "Mouse",
        "warehouse_id": "WH001",
        "quantity_on_hand": 100,
        "avg_daily_demand": 5,
        "lead_time_days": 5,
        "safety_stock": 20
    }

    response = client.post("/api/v1/inventory", json=payload)

    assert response.status_code in [200, 201]


def test_get_inventory():
    create_item()

    response = client.get("/api/v1/inventory/SKU100")

    assert response.status_code == 200


def test_low_stock():
    response = client.get("/api/v1/inventory/low-stock")

    assert response.status_code == 200


def test_simulate():
    create_item()

    response = client.post(
        "/api/v1/inventory/SKU100/simulate",
        json={
            "demand_spike_percent": 50
        }
    )

    assert response.status_code == 200


def test_delete_inventory():
    create_item()

    response = client.delete("/api/v1/inventory/SKU100")

    assert response.status_code == 200