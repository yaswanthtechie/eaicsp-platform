from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as value: yield value


def item(sku, warehouse, quantity):
    return {"sku_id": sku, "product_name": sku, "warehouse_id": warehouse, "quantity_on_hand": quantity,
            "avg_daily_demand": 5, "lead_time_days": 2, "safety_stock": 5}


def add(client, *rows):
    for row in rows: assert client.post("/api/v1/inventory", json=row).status_code == 201


def test_reorder_plan_multi_warehouse_edge_cases(client):
    add(client, item("SAME", "A", 15), item("SAME", "B", 14), item("ABOVE", "A", 16))
    plan = client.get("/api/v1/inventory/reorder-plan").json()["plan"]
    assert [(row["sku_id"], row["warehouse_id"]) for row in plan] == [("SAME", "B"), ("SAME", "A")]
    assert plan[0]["urgency_score"] == pytest.approx(.2)
    assert plan[1]["urgency_score"] == 0


def test_bulk_update_partial_failure_rolls_back_everything(client):
    add(client, item("A", "W", 10), item("B", "W", 2))
    response = client.post("/api/v1/inventory/bulk-update", json=[
        {"sku_id": "A", "warehouse_id": "W", "quantity_delta": -3},
        {"sku_id": "B", "warehouse_id": "W", "quantity_delta": -3}])
    assert response.status_code == 409
    assert client.get("/api/v1/inventory/A/W").json()["quantity_on_hand"] == 10


def test_rejected_decrement_keeps_row_visible_in_get_all(client):
    add(client, item("RETAIN", "W1", 5))
    response = client.post("/api/v1/inventory/bulk-update", json=[{
        "sku_id": "RETAIN", "warehouse_id": "W1", "quantity_delta": -10,
    }])
    assert response.status_code == 409
    all_inventory = client.get("/api/v1/inventory")
    assert all_inventory.status_code == 200
    assert len(all_inventory.json()) == 1
    assert all_inventory.json()[0]["sku_id"] == "RETAIN"
    assert all_inventory.json()[0]["quantity_on_hand"] == 5


def test_ten_concurrent_decrements_have_no_lost_updates(client):
    add(client, item("LOCK", "W", 100))
    def decrement(_):
        return client.post("/api/v1/inventory/bulk-update", json=[{"sku_id": "LOCK", "warehouse_id": "W", "quantity_delta": -1}]).status_code
    with ThreadPoolExecutor(max_workers=10) as executor: statuses = list(executor.map(decrement, range(10)))
    assert statuses == [200] * 10
    assert client.get("/api/v1/inventory/LOCK/W").json()["quantity_on_hand"] == 90


def test_what_if_returns_skus_under_spiked_point(client):
    add(client, item("SPIKE", "W", 20), item("SAFE", "W", 40))
    response = client.post("/api/v1/inventory/what-if", json={"spike_percent": 50})
    assert [row["sku_id"] for row in response.json()["affected_skus"]] == ["SPIKE"]
