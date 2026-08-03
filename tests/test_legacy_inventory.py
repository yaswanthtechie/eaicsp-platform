"""All eleven regression tests from the original single-SKU API."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def payload(sku="SKU100", quantity=40):
    return {"sku_id": sku, "product_name": "Laptop", "warehouse_id": "WH001",
            "quantity_on_hand": quantity, "avg_daily_demand": 5,
            "lead_time_days": 4, "safety_stock": 10}


def create_item():
    response = client.post("/api/v1/inventory", json=payload())
    assert response.status_code == 201
    return response.json()


def test_create_inventory():
    response = client.post("/api/v1/inventory", json=payload("SKU101", 100))
    assert response.status_code == 201
    data = response.json()
    assert data["sku_id"] == "SKU101"
    assert data["product_name"] == "Laptop"
    assert data["warehouse_id"] == "WH001"
    assert data["reorder_point"] == 30


def test_get_inventory():
    create_item()
    response = client.get("/api/v1/inventory/SKU100")
    assert response.status_code == 200
    assert response.json()["reorder_point"] == 30


def test_low_stock():
    create_item()
    response = client.get("/api/v1/inventory/low-stock")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_reorder_check():
    create_item()
    response = client.get("/api/v1/inventory/SKU100/reorder-check")
    assert response.status_code == 200
    assert response.json()["reorder_point"] == 30
    assert response.json()["needs_reorder"] is False
    assert response.json()["suggested_order_qty"] == 0


def test_simulate():
    create_item()
    response = client.post("/api/v1/inventory/SKU100/simulate", json={"demand_spike_percent": 50})
    assert response.status_code == 200
    assert {"current_quantity", "new_reorder_point", "needs_reorder", "suggested_order_qty"} <= response.json().keys()


def test_delete_inventory():
    create_item()
    assert client.delete("/api/v1/inventory/SKU100").status_code == 200
    assert client.get("/api/v1/inventory/SKU100").status_code == 404


def test_reorder_above_point():
    assert client.post("/api/v1/inventory", json=payload("SKU102", 31)).status_code == 201
    assert client.get("/api/v1/inventory/SKU102/reorder-check").json()["needs_reorder"] is False


def test_reorder_below_point():
    assert client.post("/api/v1/inventory", json=payload("SKU103", 29)).status_code == 201
    assert client.get("/api/v1/inventory/SKU103/reorder-check").json()["needs_reorder"] is True


def test_reorder_equal_point():
    assert client.post("/api/v1/inventory", json=payload("SKU104", 30)).status_code == 201
    assert client.get("/api/v1/inventory/SKU104/reorder-check").json()["needs_reorder"] is True


def test_duplicate_sku():
    assert client.post("/api/v1/inventory", json=payload("SKU200")).status_code == 201
    response = client.post("/api/v1/inventory", json=payload("SKU200"))
    assert response.status_code == 409
    assert response.json()["detail"] == "SKU already exists"


def test_suggested_order_quantity():
    assert client.post("/api/v1/inventory", json=payload("SKU201", 20)).status_code == 201
    response = client.get("/api/v1/inventory/SKU201/reorder-check")
    assert response.status_code == 200
    assert response.json()["reorder_point"] == 30
    assert response.json()["suggested_order_qty"] == 10
