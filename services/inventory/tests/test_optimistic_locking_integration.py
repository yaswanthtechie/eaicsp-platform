import concurrent.futures
import pytest

from tests.conftest import seed_sales_history, test_engine


@pytest.mark.integration
def test_concurrent_updates_optimistic_locking(client_warehouse_manager):
    """
    Milestone 1 requirement:
    Optimistic locking must work on the real database.
    Two concurrent updates hit the same item starting from version 1.
    Exactly one wins (HTTP 200, version becomes 2).
    The other gets a clear conflict error (HTTP 409, detailing version mismatch).
    """
    if test_engine.dialect.name != "postgresql":
        pytest.skip("Integration test requires PostgreSQL")

    sku_id = "CONC-OPT-WINNER"
    warehouse_id = "WH-OPT-01"

    # Seed sales history so reorder calculations work cleanly
    seed_sales_history(sku_id, warehouse_id, daily_quantity=5, days=30)

    # 1. Create the inventory item with initial version 1
    create_payload = {
        "sku_id": sku_id,
        "product_name": "Original Product",
        "warehouse_id": warehouse_id,
        "category": "Electronics",
        "quantity_on_hand": 100,
        "lead_time_days": 5,
        "safety_stock": 10,
        "warehouse_type": "local",
    }
    create_res = client_warehouse_manager.post("/api/v1/inventory/", json=create_payload)
    assert create_res.status_code == 201, f"Failed to create test inventory: {create_res.text}"
    initial_data = create_res.json()
    assert initial_data["version"] == 1
    assert initial_data["quantity_on_hand"] == 100

    # 2. Prepare two concurrent updates, BOTH starting from version 1
    update_payload_a = {
        "product_name": "Concurrent Product A",
        "quantity_on_hand": 120,
        "version": 1,
    }
    update_payload_b = {
        "product_name": "Concurrent Product B",
        "quantity_on_hand": 150,
        "version": 1,
    }

    results = []

    def perform_update(payload):
        res = client_warehouse_manager.put(
            f"/api/v1/inventory/{sku_id}/{warehouse_id}",
            json=payload,
        )
        return res.status_code, res.json()

    # 3. Execute concurrently with ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(perform_update, update_payload_a)
        future_b = executor.submit(perform_update, update_payload_b)
        results.append(future_a.result())
        results.append(future_b.result())

    # 4. Verify that exactly one wins and the other gets conflict 409
    status_codes = sorted([r[0] for r in results])
    assert status_codes == [200, 409], f"Expected exactly one 200 and one 409, got {status_codes}"

    winner = [r for r in results if r[0] == 200][0]
    conflict = [r for r in results if r[0] == 409][0]

    winner_body = winner[1]
    conflict_body = conflict[1]

    # Winner increments version to 2
    assert winner_body["version"] == 2

    # Conflict response gives a clear error message
    assert "detail" in conflict_body
    detail_msg = conflict_body["detail"]
    assert "modified by another user" in detail_msg
    assert "Current version is 2" in detail_msg
    assert "request used version 1" in detail_msg

    # 5. Verify database integrity
    get_res = client_warehouse_manager.get(f"/api/v1/inventory/{sku_id}/{warehouse_id}")
    assert get_res.status_code == 200
    final_data = get_res.json()
    assert final_data["version"] == 2
    assert final_data["quantity_on_hand"] == winner_body["quantity_on_hand"]
    assert final_data["product_name"] == winner_body["product_name"]


@pytest.mark.integration
def test_multiple_concurrent_updates_exactly_one_wins(client_warehouse_manager):
    """
    Stress test: 5 concurrent updates with version=1 on the same item.
    Exactly 1 must succeed (200, version=2), and exactly 4 must fail with 409 conflict.
    """
    if test_engine.dialect.name != "postgresql":
        pytest.skip("Integration test requires PostgreSQL")

    sku_id = "CONC-STRESS-01"
    warehouse_id = "WH-OPT-02"

    seed_sales_history(sku_id, warehouse_id, daily_quantity=5, days=30)

    create_res = client_warehouse_manager.post(
        "/api/v1/inventory/",
        json={
            "sku_id": sku_id,
            "product_name": "Multi Concurrent Base",
            "warehouse_id": warehouse_id,
            "category": "Raw Material",
            "quantity_on_hand": 50,
            "lead_time_days": 3,
            "safety_stock": 5,
            "warehouse_type": "local",
        },
    )
    assert create_res.status_code == 201

    def send_update(worker_id):
        return client_warehouse_manager.put(
            f"/api/v1/inventory/{sku_id}/{warehouse_id}",
            json={
                "product_name": f"Worker {worker_id}",
                "version": 1,
            },
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(send_update, i) for i in range(5)]
        responses = [f.result() for f in futures]

    status_counts = {}
    for r in responses:
        status_counts[r.status_code] = status_counts.get(r.status_code, 0) + 1

    assert status_counts.get(200) == 1, f"Expected exactly 1 success, got {status_counts}"
    assert status_counts.get(409) == 4, f"Expected exactly 4 conflicts, got {status_counts}"

    for r in responses:
        if r.status_code == 409:
            assert "modified by another user" in r.json()["detail"]
