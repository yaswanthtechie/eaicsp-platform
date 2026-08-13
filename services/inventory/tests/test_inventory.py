import time

from datetime import date

from app.models.sales_history import (
    SalesHistory,
)

from tests.conftest import (
    TestingSessionLocal,
    seed_sales_history,
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

def test_create_inventory(
    client,
):

    seed_sales_history(
        "SKU101",
        "WH001",
        daily_quantity=5,
    )

    response = client.post(
        "/api/v1/inventory",
        json=create_payload(
            "SKU101"
        ),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["sku_id"] == "SKU101"

    assert (
        data["warehouse_id"]
        == "WH001"
    )

    assert (
        data["avg_daily_demand"]
        == 5
    )

    # C-tier:
    # 5 * 4 + 10 = 30

    assert (
        data["reorder_point"]
        == 30
    )


# =========================================================
# MANUAL DEMAND MUST BE REJECTED
# =========================================================

def test_manual_avg_daily_demand_rejected(
    client,
):

    payload = create_payload(
        "MANUAL1",
        "WH001",
        40,
    )

    payload[
        "avg_daily_demand"
    ] = 999

    response = client.post(
        "/api/v1/inventory",
        json=payload,
    )

    assert response.status_code == 422


# =========================================================
# GET
# =========================================================

def test_get_inventory(
    client,
):

    seed_sales_history(
        "SKU100",
        "WH001",
        daily_quantity=5,
    )

    client.post(
        "/api/v1/inventory",
        json=create_payload(),
    )

    response = client.get(
        "/api/v1/inventory/"
        "SKU100/WH001"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["sku_id"]
        == "SKU100"
    )

    assert (
        data["warehouse_id"]
        == "WH001"
    )

    assert (
        data["avg_daily_demand"]
        == 5
    )


# =========================================================
# DYNAMIC REORDER
# =========================================================

def test_dynamic_reorder_point(
    client,
):

    seed_sales_history(
        "ROP1",
        "WH001",
        daily_quantity=5,
    )

    response = client.post(
        "/api/v1/inventory",
        json=create_payload(
            "ROP1",
            quantity=40,
        ),
    )

    assert response.status_code == 201

    data = response.json()

    assert (
        data["reorder_point"]
        == 30
    )


# =========================================================
# REORDER REQUIRED
# =========================================================

def test_reorder_required(
    client,
):

    seed_sales_history(
        "LOW1",
        "WH001",
        daily_quantity=5,
    )

    client.post(
        "/api/v1/inventory",
        json=create_payload(
            "LOW1",
            quantity=10,
        ),
    )

    response = client.get(
        "/api/v1/inventory/"
        "LOW1/WH001/reorder-check"
    )

    data = response.json()

    assert (
        data["reorder_point"]
        == 30
    )

    assert (
        data["needs_reorder"]
        is True
    )

    assert (
        data["suggested_order_qty"]
        == 20
    )


# =========================================================
# EXACT THRESHOLD
# =========================================================

def test_equal_reorder_point(
    client,
):

    seed_sales_history(
        "EQ1",
        "WH001",
        daily_quantity=5,
    )

    client.post(
        "/api/v1/inventory",
        json=create_payload(
            "EQ1",
            quantity=30,
        ),
    )

    response = client.get(
        "/api/v1/inventory/"
        "EQ1/WH001/reorder-check"
    )

    data = response.json()

    assert (
        data["reorder_point"]
        == 30
    )

    # Exactly at ROP:
    # no reorder

    assert (
        data["needs_reorder"]
        is False
    )

    assert (
        data["suggested_order_qty"]
        == 0
    )


# =========================================================
# MULTI WAREHOUSE
# =========================================================

def test_same_sku_multiple_warehouses(
    client,
):

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
        "/api/v1/inventory",
        json=create_payload(
            "MULTI1",
            "WH001",
            100,
        ),
    )

    second = client.post(
        "/api/v1/inventory",
        json=create_payload(
            "MULTI1",
            "WH002",
            20,
        ),
    )

    assert (
        first.status_code
        == 201
    )

    assert (
        second.status_code
        == 201
    )


# =========================================================
# REORDER PLAN
# =========================================================

def test_reorder_plan(
    client,
):

    seed_sales_history(
        "PLAN1",
        "WH001",
        daily_quantity=5,
    )

    client.post(
        "/api/v1/inventory",
        json=create_payload(
            "PLAN1",
            quantity=5,
        ),
    )

    response = client.get(
        "/api/v1/inventory/"
        "reorder-plan"
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert len(data) > 0

    assert (
        "urgency_score"
        in data[0]
    )

    assert (
        "rolling_avg_demand"
        in data[0]
    )

    assert (
        "abc_tier"
        in data[0]
    )

    assert (
        "adjusted_safety_stock"
        in data[0]
    )


# =========================================================
# LOW STOCK
# =========================================================

def test_low_stock(
    client,
):

    seed_sales_history(
        "LOW2",
        "WH001",
        daily_quantity=5,
    )

    client.post(
        "/api/v1/inventory",
        json=create_payload(
            "LOW2",
            quantity=5,
        ),
    )

    response = client.get(
        "/api/v1/inventory/"
        "low-stock"
    )

    assert (
        response.status_code
        == 200
    )

    assert isinstance(
        response.json(),
        list,
    )


# =========================================================
# SINGLE SKU SIMULATION
# =========================================================

def test_simulate(
    client,
):

    seed_sales_history(
        "SIM1",
        "WH001",
        daily_quantity=5,
    )

    client.post(
        "/api/v1/inventory",
        json=create_payload(
            "SIM1"
        ),
    )

    response = client.post(
        "/api/v1/inventory/"
        "SIM1/WH001/simulate",
        json={
            "demand_spike_percent": 50
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        "new_reorder_point"
        in data
    )


# =========================================================
# WHAT IF +30%
# =========================================================

def test_what_if(
    client,
):

    seed_sales_history(
        "WHAT1",
        "WH001",
        daily_quantity=5,
    )

    client.post(
        "/api/v1/inventory",
        json=create_payload(
            "WHAT1",
            quantity=10,
        ),
    )

    response = client.post(
        "/api/v1/inventory/"
        "what-if",
        json={
            "spike_percent": 30
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data["spike_percent"]
        == 30
    )

    assert (
        "total_items"
        in data
    )

    assert (
        "affected_items"
        in data
    )

    assert (
        "total_suggested_order_qty"
        in data
    )

    assert (
        "details"
        in data
    )


# =========================================================
# DELETE
# =========================================================

def test_delete_inventory(
    client,
):

    seed_sales_history(
        "DEL1",
        "WH001",
        daily_quantity=5,
    )

    client.post(
        "/api/v1/inventory",
        json=create_payload(
            "DEL1"
        ),
    )

    response = client.delete(
        "/api/v1/inventory/"
        "DEL1/WH001"
    )

    assert (
        response.status_code
        == 200
    )


# =========================================================
# BULK ROLLBACK
# =========================================================

def test_bulk_update_failure(
    client,
):

    seed_sales_history(
        "BULK1",
        "WH1",
        daily_quantity=5,
    )

    create_response = (
        client.post(
            "/api/v1/inventory",
            json=create_payload(
                "BULK1",
                "WH1",
                50,
            ),
        )
    )

    assert (
        create_response.status_code
        == 201
    )

    response = client.post(
        "/api/v1/inventory/"
        "bulk-update",
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

    assert (
        response.status_code
        == 409
    )

    check_response = client.get(
        "/api/v1/inventory/"
        "BULK1/WH1"
    )

    assert (
        check_response.status_code
        == 200
    )

    data = (
        check_response.json()
    )

    # First update must also be rolled back.

    assert (
        data["quantity_on_hand"]
        == 50
    )


# =========================================================
# 1000 ITEM BULK
# =========================================================

def test_bulk_update_1000_items(
    client,
):

    for i in range(1000):

        response = client.post(
            "/api/v1/inventory",
            json=create_payload(
                sku=f"LOAD{i}",
                warehouse="WHLOAD",
                quantity=100,
            ),
        )

        assert (
            response.status_code
            == 201
        )

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
        "/api/v1/inventory/"
        "bulk-update",
        json=updates,
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        len(response.json())
        == 1000
    )

    print(
        f"\n1000-item bulk update: "
        f"{elapsed:.4f} seconds"
    )


# =========================================================
# NEGATIVE DEMAND
# =========================================================

def test_negative_demand_data(
    client,
):

    db = TestingSessionLocal()

    try:

        db.add(
            SalesHistory(

                sku_id="NEG1",

                warehouse_id="WH1",

                sale_date=date.today(),

                quantity_sold=-1,
            )
        )

        db.commit()

    finally:

        db.close()

    response = client.post(
        "/api/v1/inventory",
        json=create_payload(
            "NEG1",
            "WH1",
            20,
        ),
    )

    assert (
        response.status_code
        == 400
    )

    assert (
        "Negative demand"
        in response.json()["detail"]
    )


# =========================================================
# ABC + 20% BOUNDARY
# =========================================================

def test_abc_boundary(
    client,
):

    # Total sales volume:
    #
    # A = 20%
    # B = 30%
    # C = 50%
    #
    # A cumulative = 20% exactly
    # therefore A.
    #
    # B cumulative = 50%
    # therefore B.

    seed_sales_history(
        "ABC_A",
        "WH1",
        daily_quantity=20,
    )

    seed_sales_history(
        "ABC_B",
        "WH1",
        daily_quantity=30,
    )

    seed_sales_history(
        "ABC_C",
        "WH1",
        daily_quantity=50,
    )

    for sku in [
        "ABC_A",
        "ABC_B",
        "ABC_C",
    ]:

        response = client.post(
            "/api/v1/inventory",
            json=create_payload(
                sku,
                "WH1",
                1,
            ),
        )

        assert (
            response.status_code
            == 201
        )

    response = client.get(
        "/api/v1/inventory/"
        "reorder-plan"
    )

    assert (
        response.status_code
        == 200
    )

    data = {
        item["sku_id"]: item
        for item in response.json()
    }

    assert (
        data["ABC_A"]["abc_tier"]
        == "A"
    )

    assert (
        data["ABC_B"]["abc_tier"]
        == "B"
    )

    assert (
        data["ABC_C"]["abc_tier"]
        == "C"
    )

    # Base safety stock = 10

    assert (
        data["ABC_A"][
            "adjusted_safety_stock"
        ]
        == 15
    )

    assert (
        data["ABC_B"][
            "adjusted_safety_stock"
        ]
        == 12
    )

    assert (
        data["ABC_C"][
            "adjusted_safety_stock"
        ]
        == 10
    )


# =========================================================
# TRANSFER
# =========================================================

def test_transfer_suggestion(
    client,
):

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

    # Source = 100
    client.post(
        "/api/v1/inventory",
        json=create_payload(
            "TR1",
            "SOURCE",
            100,
        ),
    )

    # Destination = 5
    client.post(
        "/api/v1/inventory",
        json=create_payload(
            "TR1",
            "DEST",
            5,
        ),
    )

    response = client.get(
        "/api/v1/inventory/"
        "reorder-plan"
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    destination = next(
        item
        for item in data
        if item["warehouse_id"]
        == "DEST"
    )

    transfer = (
        destination[
            "transfer_suggestion"
        ]
    )

    assert transfer is not None

    assert (
        transfer[
            "source_warehouse"
        ]
        == "SOURCE"
    )

    assert (
        transfer[
            "destination_warehouse"
        ]
        == "DEST"
    )

    assert (
        transfer[
            "recommendation"
        ]
        == "TRANSFER"
    )


# =========================================================
# UPDATE
# =========================================================

def test_update_inventory(
    client,
):

    seed_sales_history(
        "UPD1",
        "WH1",
        daily_quantity=5,
    )

    response = client.post(
        "/api/v1/inventory",
        json=create_payload(
            "UPD1",
            "WH1",
            50,
        ),
    )

    assert (
        response.status_code
        == 201
    )

    response = client.put(
        "/api/v1/inventory/"
        "UPD1/WH1",
        json={
            "quantity_on_hand": 20,
            "lead_time_days": 6,
            "safety_stock": 20,
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    # Demand comes from SalesHistory.
    # Changing inventory settings does
    # not change sales demand.

    assert (
        data["avg_daily_demand"]
        == 5
    )


# =========================================================
# MANUAL DEMAND UPDATE MUST FAIL
# =========================================================

def test_manual_demand_update_rejected(
    client,
):

    seed_sales_history(
        "UPD2",
        "WH1",
        daily_quantity=5,
    )

    client.post(
        "/api/v1/inventory",
        json=create_payload(
            "UPD2",
            "WH1",
            50,
        ),
    )

    response = client.put(
        "/api/v1/inventory/"
        "UPD2/WH1",
        json={
            "avg_daily_demand": 999
        },
    )

    assert (
        response.status_code
        == 422
    )
def test_reorder_exactly_at_threshold(client):
    payload = {
        "sku_id": "SKU-THRESHOLD",
        "product_name": "Threshold Product",
        "warehouse_id": "WH001",
        "quantity_on_hand": 50,
        "lead_time_days": 4,
        "safety_stock": 10,
    }

    response = client.post(
        "/api/v1/inventory/",
        json=payload,
    )
    print(response.json())

    assert response.status_code in (200, 201)

    response = client.get(
        "/api/v1/inventory/reorder-plan"
    )

    assert response.status_code == 200

    data = response.json()

    matching = [
        item
        for item in data
        if item["sku_id"] == "SKU-THRESHOLD"
    ]

    # ROP = (10 × 4) + 10 = 50
    # Quantity on hand = 50
    # Exactly at ROP means it should NOT be in reorder plan.
    assert matching == []

def test_simulate_30_percent_growth(client):
    response = client.get(
        "/api/v1/inventory/simulate?growth_percent=30"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["growth_percent"] == 30
    assert "total_inventory_items" in data
    assert "total_current_daily_demand" in data
    assert "total_simulated_daily_demand" in data
    assert "additional_daily_demand" in data
    assert "items" in data

    assert (
        data["total_simulated_daily_demand"]
        >= data["total_current_daily_demand"]
    )


def test_simulation_does_not_modify_inventory(client):
    response = client.get(
        "/api/v1/inventory/"
    )

    assert response.status_code == 200

    before_data = response.json()

    response = client.get(
        "/api/v1/inventory/simulate?growth_percent=30"
    )

    assert response.status_code == 200

    response = client.get(
        "/api/v1/inventory/"
    )

    assert response.status_code == 200

    after_data = response.json()

    assert len(before_data) == len(after_data)

    before_items = {
        (
            item["sku_id"],
            item["warehouse_id"],
        ): item
        for item in before_data
    }

    after_items = {
        (
            item["sku_id"],
            item["warehouse_id"],
        ): item
        for item in after_data
    }

    assert before_items == after_items


def test_simulate_negative_growth(client):
    response = client.get(
        "/api/v1/inventory/simulate?growth_percent=-30"
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Growth percentage cannot be negative"
    )


def test_simulate_zero_growth(client):
    response = client.get(
        "/api/v1/inventory/simulate?growth_percent=0"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["growth_percent"] == 0

    assert (
        data["total_current_daily_demand"]
        == data["total_simulated_daily_demand"]
    )


def test_simulate_empty_inventory(client):
    response = client.get(
        "/api/v1/inventory/simulate?growth_percent=30"
    )

    assert response.status_code == 200

    data = response.json()

    assert "total_inventory_items" in data
    assert "items" in data

    if data["total_inventory_items"] == 0:
        assert data["items"] == []
        assert (
            data["total_current_daily_demand"]
            == 0
        )
        assert (
            data["total_simulated_daily_demand"]
            == 0
        )
def test_negative_demand_is_rejected(client):
    from app.services import demand_service

    original_function = (
        demand_service.calculate_rolling_average_demand
    )

    def negative_demand(*args, **kwargs):
        return -10.0

    demand_service.calculate_rolling_average_demand = (
        negative_demand
    )

    try:
        payload = {
            "sku_id": "NEG-DEMAND-001",
            "product_name": "Negative Demand Test",
            "warehouse_id": "WH001",
            "quantity_on_hand": 50,
            "lead_time_days": 4,
            "safety_stock": 10,
        }

        response = client.post(
            "/api/v1/inventory/",
            json=payload,
        )

        assert response.status_code == 400

        data = response.json()

        assert data["detail"] == "Demand cannot be negative"

    finally:
        demand_service.calculate_rolling_average_demand = (
            original_function
        )
        
        
def test_bulk_update_partial_failure_rolls_back(
    client,
):
    first_payload = {
        "sku_id": "ROLLBACK-001",
        "product_name": "Rollback One",
        "warehouse_id": "WH001",
        "quantity_on_hand": 100,
        "lead_time_days": 5,
        "safety_stock": 10,
    }

    second_payload = {
        "sku_id": "ROLLBACK-002",
        "product_name": "Rollback Two",
        "warehouse_id": "WH001",
        "quantity_on_hand": 200,
        "lead_time_days": 5,
        "safety_stock": 10,
    }

    response = client.post(
        "/api/v1/inventory/",
        json=first_payload,
    )

    assert response.status_code in (200, 201)

    response = client.post(
        "/api/v1/inventory/",
        json=second_payload,
    )

    assert response.status_code in (200, 201)

    bulk_payload = {
        "updates": [
            {
                "sku_id": "ROLLBACK-001",
                "warehouse_id": "WH001",
                "quantity_on_hand": 500,
            },
            {
                "sku_id": "DOES-NOT-EXIST",
                "warehouse_id": "WH001",
                "quantity_on_hand": 999,
            },
        ]
    }

    response = client.put(
        "/api/v1/inventory/bulk-update",
        json=bulk_payload,
    )

    assert response.status_code >= 400

    response = client.get(
        "/api/v1/inventory/"
        "ROLLBACK-001/WH001"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["quantity_on_hand"] == 100
    
    
def test_abc_exactly_at_20_percentile(
    client,
):
    from app.services.abc_service import (
        classify_skus,
    )

    result = classify_skus(
        client.app.state.db
    )

    assert result is not None

def test_abc_exactly_at_20_percent_boundary(
    db_session,
):
    from app.models.sales_history import SalesHistory
    from app.services.abc_service import classify_skus

    records = [
        SalesHistory(
            sku_id="ABC001",
            warehouse_id="WH001",
            sale_date=date(2026, 8, 1),
            quantity_sold=20,
),
        SalesHistory(
            sku_id="ABC002",
            warehouse_id="WH001",
            sale_date=date(2026, 8, 1),
            quantity_sold=80,
        ),
    ]

    db_session.add_all(records)
    db_session.commit()

    result = classify_skus(db_session)

    item = result[
        ("ABC001", "WH001")
    ]

    assert item["sales_volume"] == 20

    assert (
        item["cumulative_percentage"]
        == 20.0
    )

    assert item["abc_tier"] == "A"