import threading
import time
from datetime import date

import pytest

from app.models.inventory import Inventory
from app.models.sales_history import SalesHistory
from app.services.abc_service import classify_skus

from tests.conftest import (
    TestingSessionLocal,
    seed_sales_history,
    test_engine,
)


# =========================================================
# TEST PAYLOAD
# =========================================================

def create_payload(
    sku="SKU100",
    warehouse="WH001",
    quantity=40,
):
    return {
        "sku_id": sku,
        "product_name": "Laptop",
        "warehouse_id": warehouse,
        "quantity_on_hand": quantity,
        "lead_time_days": 4,
        "safety_stock": 10,
    }


# =========================================================
# CREATE
# =========================================================

def test_create_inventory(client):

    seed_sales_history(
        "SKU101",
        "WH001",
        daily_quantity=5,
    )

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload("SKU101"),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["sku_id"] == "SKU101"
    assert data["warehouse_id"] == "WH001"
    assert data["avg_daily_demand"] == 5
    assert data["reorder_point"] >= 30


# =========================================================
# MANUAL DEMAND MUST BE REJECTED
# =========================================================

def test_manual_avg_daily_demand_rejected(client):

    payload = create_payload(
        "MANUAL1",
        "WH001",
        40,
    )

    payload["avg_daily_demand"] = 999

    response = client.post(
        "/api/v1/inventory/",
        json=payload,
    )

    assert response.status_code == 422


# =========================================================
# GET SINGLE INVENTORY
# =========================================================

def test_get_inventory(client):

    seed_sales_history(
        "SKU100",
        "WH001",
        daily_quantity=5,
    )

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload(),
    )

    assert response.status_code == 201

    response = client.get(
        "/api/v1/inventory/SKU100/WH001"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["sku_id"] == "SKU100"
    assert data["warehouse_id"] == "WH001"
    assert data["avg_daily_demand"] == 5


# =========================================================
# DYNAMIC REORDER POINT
# =========================================================

def test_dynamic_reorder_point(client):

    seed_sales_history(
        "ROP1",
        "WH001",
        daily_quantity=5,
    )

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload(
            "ROP1",
            quantity=40,
        ),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["avg_daily_demand"] == 5

    # Base:
    # 5 * 4 + 10 = 30
    #
    # ABC adjustment may make it higher.
    assert data["reorder_point"] >= 30


# =========================================================
# REORDER REQUIRED
# =========================================================

def test_reorder_required(client):

    seed_sales_history(
        "LOW1",
        "WH001",
        daily_quantity=5,
    )

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload(
            "LOW1",
            quantity=10,
        ),
    )

    assert response.status_code == 201

    response = client.get(
        "/api/v1/inventory/LOW1/WH001/reorder-check"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["reorder_point"] >= 30
    assert data["needs_reorder"] is True
    assert data["suggested_order_qty"] > 0


# =========================================================
# EXACT REORDER THRESHOLD
# =========================================================

def test_reorder_exactly_at_threshold(client):

    seed_sales_history(
        "SKU-THRESHOLD",
        "WH001",
        daily_quantity=10,
    )

    payload = {
        "sku_id": "SKU-THRESHOLD",
        "product_name": "Threshold Product",
        "warehouse_id": "WH001",
        "quantity_on_hand": 100,
        "lead_time_days": 4,
        "safety_stock": 10,
    }

    response = client.post(
        "/api/v1/inventory/",
        json=payload,
    )

    assert response.status_code == 201

    created = response.json()

    # Use the actual reorder point calculated by the service.
    reorder_point = created["reorder_point"]

    assert reorder_point > 0

    # Put stock exactly at the calculated reorder point.
    response = client.put(
        "/api/v1/inventory/"
        "SKU-THRESHOLD/WH001",
        json={
            "quantity_on_hand": reorder_point,
        },
    )

    assert response.status_code == 200

    check = client.get(
        "/api/v1/inventory/"
        "SKU-THRESHOLD/WH001/reorder-check"
    )

    assert check.status_code == 200

    data = check.json()

    assert data["current_qty"] == reorder_point
    assert data["reorder_point"] == reorder_point
    assert data["needs_reorder"] is False
    assert data["suggested_order_qty"] == 0

    # Exactly at ROP must not appear in reorder plan.
    plan_response = client.get(
        "/api/v1/inventory/reorder-plan"
    )

    assert plan_response.status_code == 200

    matching = [
        item
        for item in plan_response.json()
        if item["sku_id"] == "SKU-THRESHOLD"
        and item["warehouse_id"] == "WH001"
    ]

    assert matching == []
# =========================================================
# ONE UNIT BELOW REORDER THRESHOLD
# =========================================================

def test_reorder_one_unit_below_threshold(client):

    seed_sales_history(
        "SKU-BELOW",
        "WH001",
        daily_quantity=10,
    )

    payload = {
        "sku_id": "SKU-BELOW",
        "product_name": "Below Threshold Product",
        "warehouse_id": "WH001",
        "quantity_on_hand": 100,
        "lead_time_days": 4,
        "safety_stock": 10,
    }

    response = client.post(
        "/api/v1/inventory/",
        json=payload,
    )

    assert response.status_code == 201

    created = response.json()

    reorder_point = created["reorder_point"]

    assert reorder_point > 0

    # Exactly one unit below ROP.
    quantity_below = reorder_point - 1

    assert quantity_below >= 0

    response = client.put(
        "/api/v1/inventory/"
        "SKU-BELOW/WH001",
        json={
            "quantity_on_hand": quantity_below,
        },
    )

    assert response.status_code == 200

    check = client.get(
        "/api/v1/inventory/"
        "SKU-BELOW/WH001/reorder-check"
    )

    assert check.status_code == 200

    data = check.json()

    assert data["current_qty"] == quantity_below
    assert data["reorder_point"] == reorder_point
    assert data["needs_reorder"] is True
    assert data["suggested_order_qty"] == 1

    # It must now appear in reorder plan.
    plan_response = client.get(
        "/api/v1/inventory/reorder-plan"
    )

    assert plan_response.status_code == 200

    matching = [
        item
        for item in plan_response.json()
        if item["sku_id"] == "SKU-BELOW"
        and item["warehouse_id"] == "WH001"
    ]

    assert len(matching) == 1

# =========================================================
# MULTI WAREHOUSE
# =========================================================

def test_same_sku_multiple_warehouses(client):

    seed_sales_history(
        "MULTI1",
        "WH001",
        daily_quantity=5,
    )

    seed_sales_history(
        "MULTI1",
        "WH002",
        daily_quantity=3,
    )

    first = client.post(
        "/api/v1/inventory/",
        json=create_payload(
            "MULTI1",
            "WH001",
            100,
        ),
    )

    second = client.post(
        "/api/v1/inventory/",
        json=create_payload(
            "MULTI1",
            "WH002",
            20,
        ),
    )

    assert first.status_code == 201
    assert second.status_code == 201


# =========================================================
# REORDER PLAN
# =========================================================

def test_reorder_plan(client):

    seed_sales_history(
        "PLAN1",
        "WH001",
        daily_quantity=5,
    )

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload(
            "PLAN1",
            quantity=5,
        ),
    )

    assert response.status_code == 201

    response = client.get(
        "/api/v1/inventory/reorder-plan"
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) > 0

    item = next(
        item
        for item in data
        if item["sku_id"] == "PLAN1"
    )

    assert "urgency_score" in item
    assert "rolling_avg_demand" in item
    assert "abc_tier" in item
    assert "adjusted_safety_stock" in item


# =========================================================
# LOW STOCK
# =========================================================

def test_low_stock(client):

    seed_sales_history(
        "LOW2",
        "WH001",
        daily_quantity=5,
    )

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload(
            "LOW2",
            quantity=5,
        ),
    )

    assert response.status_code == 201

    response = client.get(
        "/api/v1/inventory/low-stock"
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


# =========================================================
# SINGLE SKU SIMULATION
# =========================================================

def test_simulate(client):

    seed_sales_history(
        "SIM1",
        "WH001",
        daily_quantity=5,
    )

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload("SIM1"),
    )

    assert response.status_code == 201

    response = client.post(
        "/api/v1/inventory/"
        "SIM1/WH001/simulate",
        json={
            "demand_spike_percent": 50,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["sku_id"] == "SIM1"
    assert "new_reorder_point" in data
    assert "needs_reorder" in data
    assert "suggested_order_qty" in data


# =========================================================
# WHAT-IF +30%
# =========================================================

def test_what_if(client):

    seed_sales_history(
        "WHAT1",
        "WH001",
        daily_quantity=5,
    )

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload(
            "WHAT1",
            quantity=10,
        ),
    )

    assert response.status_code == 201

    response = client.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent": 30,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["spike_percent"] == 30
    assert "total_items" in data
    assert "affected_items" in data
    assert "total_suggested_order_qty" in data
    assert "details" in data


# =========================================================
# DELETE
# =========================================================

def test_delete_inventory(client):

    seed_sales_history(
        "DEL1",
        "WH001",
        daily_quantity=5,
    )

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload("DEL1"),
    )

    assert response.status_code == 201

    response = client.delete(
        "/api/v1/inventory/DEL1/WH001"
    )

    assert response.status_code == 200

    response = client.get(
        "/api/v1/inventory/DEL1/WH001"
    )

    assert response.status_code == 404


# =========================================================
# BULK UPDATE ROLLBACK
# =========================================================

def test_bulk_update_failure(client):

    seed_sales_history(
        "BULK1",
        "WH1",
        daily_quantity=5,
    )

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload(
            "BULK1",
            "WH1",
            50,
        ),
    )

    assert response.status_code == 201

    response = client.post(
        "/api/v1/inventory/bulk-update",
        json=[
            {
                "sku_id": "BULK1",
                "warehouse_id": "WH1",
                "quantity_delta": -10,
            },
            {
                "sku_id": "INVALID",
                "warehouse_id": "WH1",
                "quantity_delta": -10,
            },
        ],
    )

    assert response.status_code == 409

    response = client.get(
        "/api/v1/inventory/BULK1/WH1"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["quantity_on_hand"] == 50


# =========================================================
# 1000 ITEM BULK UPDATE
# =========================================================

def test_bulk_update_1000_items(client):

    db = TestingSessionLocal()

    try:

        inventory_records = [
            Inventory(
                sku_id=f"LOAD{i}",
                product_name="Load Test Product",
                warehouse_id="WHLOAD",
                quantity_on_hand=100,
                avg_daily_demand=0.0,
                lead_time_days=4,
                safety_stock=10,
            )
            for i in range(1000)
        ]

        db.bulk_save_objects(
            inventory_records
        )

        db.commit()

    finally:
        db.close()

    updates = [
        {
            "sku_id": f"LOAD{i}",
            "warehouse_id": "WHLOAD",
            "quantity_delta": -1,
        }
        for i in range(1000)
    ]

    start = time.perf_counter()

    response = client.post(
        "/api/v1/inventory/bulk-update",
        json=updates,
    )

    elapsed = time.perf_counter() - start

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1000

    print(
        f"\n1000-item bulk update: "
        f"{elapsed:.4f} seconds"
    )


# =========================================================
# NEGATIVE DEMAND
# =========================================================

# =========================================================
# NEGATIVE DEMAND MUST NOT CREATE INVENTORY
# =========================================================

def test_negative_demand_is_rejected(client):

    db = TestingSessionLocal()

    try:
        db.add(
            SalesHistory(
                sku_id="NEG-DEMAND-001",
                warehouse_id="WH001",
                sale_date=date.today(),
                quantity_sold=-10,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/v1/inventory/",
        json={
            "sku_id": "NEG-DEMAND-001",
            "product_name": "Negative Demand Test",
            "warehouse_id": "WH001",
            "quantity_on_hand": 50,
            "lead_time_days": 4,
            "safety_stock": 10,
        },
    )

    assert response.status_code == 400
    assert "Negative demand" in response.json()["detail"]

    # Failed transaction must not leave inventory behind.
    follow_up = client.get(
        "/api/v1/inventory/"
        "NEG-DEMAND-001/WH001"
    )

    assert follow_up.status_code == 404
# =========================================================
# ABC 20TH PERCENTILE BOUNDARY
# =========================================================

# =========================================================
# ABC 20% BOUNDARY
# =========================================================

def test_abc_exactly_at_20th_percentile(db_session):

    for rank in range(1, 11):

        db_session.add(
            SalesHistory(
                sku_id=f"ABC-RANK-{rank:02d}",
                warehouse_id="WH001",
                sale_date=date(2026, 8, 1),
                quantity_sold=(11 - rank) * 100,
            )
        )

    db_session.commit()

    result = classify_skus(db_session)

    # Highest-selling SKU.
    assert (
        result[("ABC-RANK-01", "WH001")]["abc_tier"]
        == "A"
    )

    # Exactly 20th percentile must still be A.
    assert (
        result[("ABC-RANK-02", "WH001")]["rank_percentile"]
        == 20.0
    )

    assert (
        result[("ABC-RANK-02", "WH001")]["abc_tier"]
        == "A"
    )

    # 30th percentile is B.
    assert (
        result[("ABC-RANK-03", "WH001")]["rank_percentile"]
        == 30.0
    )

    assert (
        result[("ABC-RANK-03", "WH001")]["abc_tier"]
        == "B"
    )

    # Worst seller must be C.
    assert (
        result[("ABC-RANK-10", "WH001")]["abc_tier"]
        == "C"
    )

# =========================================================
# TRANSFER SUGGESTION
# =========================================================

def test_transfer_suggestion(client):

    seed_sales_history(
        "TR1",
        "SOURCE",
        daily_quantity=5,
    )

    seed_sales_history(
        "TR1",
        "DEST",
        daily_quantity=5,
    )

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload(
            "TR1",
            "SOURCE",
            100,
        ),
    )

    assert response.status_code == 201

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload(
            "TR1",
            "DEST",
            5,
        ),
    )

    assert response.status_code == 201

    response = client.get(
        "/api/v1/inventory/reorder-plan"
    )

    assert response.status_code == 200

    data = response.json()

    destination = next(
        item
        for item in data
        if item["warehouse_id"] == "DEST"
    )

    transfer = (
        destination["transfer_suggestion"]
    )

    assert transfer is not None

    assert (
        transfer["source_warehouse"]
        == "SOURCE"
    )

    assert (
        transfer["destination_warehouse"]
        == "DEST"
    )

    assert (
        transfer["recommendation"]
        == "TRANSFER"
    )

    assert (
        transfer["transfer_quantity"]
        > 0
    )


# =========================================================
# UPDATE
# =========================================================

def test_update_inventory(client):

    seed_sales_history(
        "UPD1",
        "WH1",
        daily_quantity=5,
    )

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload(
            "UPD1",
            "WH1",
            50,
        ),
    )

    assert response.status_code == 201

    response = client.put(
        "/api/v1/inventory/UPD1/WH1",
        json={
            "quantity_on_hand": 20,
            "lead_time_days": 6,
            "safety_stock": 20,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["avg_daily_demand"] == 5


# =========================================================
# MANUAL DEMAND UPDATE MUST FAIL
# =========================================================

def test_manual_demand_update_rejected(client):

    seed_sales_history(
        "UPD2",
        "WH1",
        daily_quantity=5,
    )

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload(
            "UPD2",
            "WH1",
            50,
        ),
    )

    assert response.status_code == 201

    response = client.put(
        "/api/v1/inventory/UPD2/WH1",
        json={
            "avg_daily_demand": 999,
        },
    )

    assert response.status_code == 422


# =========================================================
# SIMULATION +30%
# =========================================================

def test_simulate_30_percent_growth(client):

    seed_sales_history(
        "SIM-GROWTH",
        "WH001",
        daily_quantity=10,
    )

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload(
            "SIM-GROWTH",
            "WH001",
            50,
        ),
    )

    assert response.status_code == 201

    response = client.get(
        "/api/v1/inventory/simulate"
        "?growth_percent=30"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["growth_percent"] == 30

    assert (
        data["total_inventory_items"]
        == 1
    )

    assert (
        data["total_simulated_daily_demand"]
        >= data["total_current_daily_demand"]
    )

    assert (
        data["additional_daily_demand"]
        >= 0
    )

    assert len(data["items"]) == 1


# =========================================================
# SIMULATION MUST NOT MODIFY INVENTORY
# =========================================================

def test_simulation_does_not_modify_inventory(
    client,
):

    seed_sales_history(
        "SIM-NOMODIFY",
        "WH001",
        daily_quantity=10,
    )

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload(
            "SIM-NOMODIFY",
            "WH001",
            50,
        ),
    )

    assert response.status_code == 201

    response = client.get(
        "/api/v1/inventory/"
    )

    assert response.status_code == 200

    before_data = response.json()

    response = client.get(
        "/api/v1/inventory/simulate"
        "?growth_percent=30"
    )

    assert response.status_code == 200

    response = client.get(
        "/api/v1/inventory/"
    )

    assert response.status_code == 200

    after_data = response.json()

    assert before_data == after_data


# =========================================================
# NEGATIVE SIMULATION GROWTH
# =========================================================

def test_simulate_negative_growth(client):

    response = client.get(
        "/api/v1/inventory/simulate"
        "?growth_percent=-30"
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Growth percentage cannot be negative"
    )


# =========================================================
# ZERO SIMULATION GROWTH
# =========================================================

def test_simulate_zero_growth(client):

    seed_sales_history(
        "SIM-ZERO",
        "WH001",
        daily_quantity=10,
    )

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload(
            "SIM-ZERO",
            "WH001",
            50,
        ),
    )

    assert response.status_code == 201

    response = client.get(
        "/api/v1/inventory/simulate"
        "?growth_percent=0"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["growth_percent"] == 0

    assert (
        data["total_current_daily_demand"]
        == data["total_simulated_daily_demand"]
    )


# =========================================================
# EMPTY INVENTORY SIMULATION
# =========================================================

def test_simulate_empty_inventory(client):

    response = client.get(
        "/api/v1/inventory/simulate"
        "?growth_percent=30"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["total_inventory_items"]
        == 0
    )

    assert data["items"] == []

    assert (
        data["total_current_daily_demand"]
        == 0
    )

    assert (
        data["total_simulated_daily_demand"]
        == 0
    )

    assert (
        data["additional_daily_demand"]
        == 0
    )


# =========================================================
# CONCURRENT DECREMENT
# =========================================================

def test_concurrent_decrement_does_not_lose_updates(
    client,
):

    if test_engine.dialect.name != "postgresql":
        pytest.skip(
            "Row locking requires PostgreSQL"
        )

    seed_sales_history(
        "CONC1",
        "WH001",
        daily_quantity=5,
    )

    response = client.post(
        "/api/v1/inventory/",
        json=create_payload(
            "CONC1",
            "WH001",
            100,
        ),
    )

    assert response.status_code == 201

    responses = []
    lock = threading.Lock()

    def decrement():

        response = client.post(
            "/api/v1/inventory/decrement"
            "?sku_id=CONC1"
            "&warehouse_id=WH001"
            "&quantity=1"
        )

        with lock:
            responses.append(
                response.status_code
            )

    threads = [
        threading.Thread(
            target=decrement
        )
        for _ in range(10)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert sorted(responses) == [200] * 10

    final = client.get(
        "/api/v1/inventory/"
        "CONC1/WH001"
    )

    assert final.status_code == 200

    data = final.json()

    assert data["quantity_on_hand"] == 90


# =========================================================
# CSV MISSING COLUMNS
# =========================================================

def test_csv_rejects_missing_columns(client):

    csv_content = (
        "sku_id,product_name,warehouse_id\n"
        "CSV-001,Laptop,WH001\n"
    )

    response = client.post(
        "/api/v1/inventory/bulk-upload",
        files={
            "file": (
                "inventory.csv",
                csv_content,
                "text/csv",
            )
        },
    )

    assert response.status_code == 400


# =========================================================
# CSV NEGATIVE QUANTITY
# =========================================================

def test_csv_rejects_negative_quantity(client):

    csv_content = (
        "sku_id,product_name,warehouse_id,"
        "quantity_on_hand,lead_time_days,safety_stock\n"
        "CSV-NEG,Laptop,WH001,-500,4,10\n"
    )

    response = client.post(
        "/api/v1/inventory/bulk-upload",
        files={
            "file": (
                "inventory.csv",
                csv_content,
                "text/csv",
            )
        },
    )

    assert response.status_code == 400