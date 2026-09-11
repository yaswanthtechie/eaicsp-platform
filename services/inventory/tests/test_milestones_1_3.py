
from datetime import datetime, timedelta

import pytest

from app.models.inventory import Inventory
from app.models.inventory_cost_layer import InventoryCostLayer
from app.models.supplier import Supplier

from tests.conftest import seed_sales_history


# ============================================================
# MILESTONE 1 — MULTI-ECHELON INVENTORY
# ============================================================


def test_m1_create_inventory_hierarchy(client, db_session):
    """
    Create a central -> regional -> local warehouse hierarchy.
    """

    sku = "SKU-M1-HIERARCHY"

    central = {
        "sku_id": sku,
        "product_name": "M1 Product",
        "warehouse_id": "WH-CENTRAL",
        "category": "Electronics",
        "quantity_on_hand": 500,
        "lead_time_days": 5,
        "safety_stock": 20,
        "warehouse_type": "central",
    }

    regional = {
        "sku_id": sku,
        "product_name": "M1 Product",
        "warehouse_id": "WH-REGIONAL",
        "category": "Electronics",
        "quantity_on_hand": 100,
        "lead_time_days": 5,
        "safety_stock": 20,
        "warehouse_type": "regional",
        "parent_warehouse_id": "WH-CENTRAL",
    }

    local = {
        "sku_id": sku,
        "product_name": "M1 Product",
        "warehouse_id": "WH-LOCAL",
        "category": "Electronics",
        "quantity_on_hand": 10,
        "lead_time_days": 5,
        "safety_stock": 10,
        "warehouse_type": "local",
        "parent_warehouse_id": "WH-REGIONAL",
    }

    response = client.post(
        "/api/v1/inventory",
        json=central,
    )

    assert response.status_code == 201

    response = client.post(
        "/api/v1/inventory",
        json=regional,
    )

    assert response.status_code == 201

    response = client.post(
        "/api/v1/inventory",
        json=local,
    )

    assert response.status_code == 201


def test_m1_reorder_plan_contains_transfer_suggestion(
    client,
    db_session,
):
    """
    Reorder plan is a catalogue-level endpoint.

    It checks all inventory records and can suggest
    transferring stock from another warehouse.
    """

    sku = "SKU-M1-TRANSFER"

    source = Inventory(
        sku_id=sku,
        warehouse_id="WH-SOURCE",
        product_name="Transfer Product",
        category="Electronics",
        quantity_on_hand=200,
        avg_daily_demand=5,
        lead_time_days=5,
        safety_stock=10,
        warehouse_type="regional",
    )

    destination = Inventory(
        sku_id=sku,
        warehouse_id="WH-LOCAL",
        product_name="Transfer Product",
        category="Electronics",
        quantity_on_hand=1,
        avg_daily_demand=10,
        lead_time_days=5,
        safety_stock=20,
        warehouse_type="local",
        parent_warehouse_id="WH-SOURCE",
    )

    db_session.add_all(
        [
            source,
            destination,
        ]
    )

    db_session.commit()

    seed_sales_history(
        sku_id=sku,
        warehouse_id="WH-LOCAL",
        daily_quantity=10,
        days=30,
    )

    response = client.get(
        "/api/v1/inventory/reorder-plan"
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)

    matching_item = None

    for item in data:
        if (
            item["sku_id"] == sku
            and item["warehouse_id"] == "WH-LOCAL"
        ):
            matching_item = item
            break

    assert matching_item is not None

    assert (
        matching_item["transfer_suggestion"]
        is not None
    )


def test_m1_fulfill_shortage_from_parent_warehouse(
    client,
    db_session,
):
    """
    A local warehouse shortage should be fulfilled
    from its parent warehouse when stock is available.
    """

    sku = "SKU-M1-FULFILL"

    parent = Inventory(
        sku_id=sku,
        warehouse_id="WH-PARENT",
        product_name="Fulfill Product",
        category="Electronics",
        quantity_on_hand=100,
        avg_daily_demand=5,
        lead_time_days=5,
        safety_stock=10,
        warehouse_type="regional",
    )

    child = Inventory(
        sku_id=sku,
        warehouse_id="WH-CHILD",
        product_name="Fulfill Product",
        category="Electronics",
        quantity_on_hand=5,
        avg_daily_demand=5,
        lead_time_days=5,
        safety_stock=10,
        warehouse_type="local",
        parent_warehouse_id="WH-PARENT",
    )

    db_session.add_all(
        [
            parent,
            child,
        ]
    )

    db_session.commit()

    response = client.post(
        "/api/v1/inventory/multi-echelon/fulfill",
        params={
            "sku_id": sku,
            "warehouse_id": "WH-CHILD",
            "required_quantity": 20,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["sku_id"] == sku
    assert data["warehouse_id"] == "WH-CHILD"
    assert data["required_quantity"] == 20


def test_m1_fulfill_rejects_invalid_quantity(client):
    response = client.post(
        "/api/v1/inventory/multi-echelon/fulfill",
        params={
            "sku_id": "SKU-M1-INVALID",
            "warehouse_id": "WH-LOCAL",
            "required_quantity": 0,
        },
    )

    assert response.status_code == 400


# ============================================================
# MILESTONE 2 — AUTOMATIC DRAFT PURCHASE ORDER
# ============================================================


def test_m2_automatic_draft_po_selects_lowest_cost_supplier(
    client,
    db_session,
):
    """
    The automatic PO should select the cheapest supplier
    for the requested SKU.
    """

    sku = "SKU-M2-SUPPLIER"

    inventory = Inventory(
        sku_id=sku,
        warehouse_id="WH-M2",
        product_name="M2 Product",
        category="Electronics",
        quantity_on_hand=1,
        avg_daily_demand=10,
        lead_time_days=5,
        safety_stock=10,
        warehouse_type="local",
    )

    expensive_supplier = Supplier(
        supplier_id="SUP-M2-EXPENSIVE",
        sku_id=sku,
        supplier_name="Expensive Supplier",
        unit_cost=100.0,
        lead_time_days=5,
    )

    cheap_supplier = Supplier(
        supplier_id="SUP-M2-CHEAP",
        sku_id=sku,
        supplier_name="Cheap Supplier",
        unit_cost=50.0,
        lead_time_days=5,
    )

    db_session.add_all(
        [
            inventory,
            expensive_supplier,
            cheap_supplier,
        ]
    )

    db_session.commit()

    seed_sales_history(
        sku_id=sku,
        warehouse_id="WH-M2",
        daily_quantity=10,
        days=30,
    )

    response = client.post(
        "/api/v1/purchase-orders/draft",
        json={
            "sku_id": sku,
            "warehouse_id": "WH-M2",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["supplier_id"] == "SUP-M2-CHEAP"
    assert data["unit_cost"] == 50.0


def test_m2_automatic_po_contains_expected_cost(
    client,
    db_session,
):
    """
    Expected cost must equal:

        suggested quantity * supplier unit cost
    """

    sku = "SKU-M2-COST"

    inventory = Inventory(
        sku_id=sku,
        warehouse_id="WH-M2-COST",
        product_name="Cost Product",
        category="Electronics",
        quantity_on_hand=1,
        avg_daily_demand=10,
        lead_time_days=5,
        safety_stock=10,
        warehouse_type="local",
    )

    supplier = Supplier(
        supplier_id="SUP-M2-COST",
        sku_id=sku,
        supplier_name="Cost Supplier",
        unit_cost=25.0,
        lead_time_days=5,
    )

    db_session.add_all(
        [
            inventory,
            supplier,
        ]
    )

    db_session.commit()

    seed_sales_history(
        sku_id=sku,
        warehouse_id="WH-M2-COST",
        daily_quantity=10,
        days=30,
    )

    response = client.post(
        "/api/v1/purchase-orders/draft",
        json={
            "sku_id": sku,
            "warehouse_id": "WH-M2-COST",
        },
    )

    assert response.status_code == 201

    data = response.json()

    expected_cost = (
        data["quantity"] * data["unit_cost"]
    )

    assert data["expected_cost"] == expected_cost


def test_m2_automatic_po_fails_when_inventory_not_found(
    client,
):
    response = client.post(
        "/api/v1/purchase-orders/draft",
        json={
            "sku_id": "SKU-M2-NOT-FOUND",
            "warehouse_id": "WH-MISSING",
        },
    )

    assert response.status_code == 400


def test_m2_automatic_po_fails_when_no_supplier_exists(
    client,
    db_session,
):
    sku = "SKU-M2-NO-SUPPLIER"

    inventory = Inventory(
        sku_id=sku,
        warehouse_id="WH-M2-NO-SUP",
        product_name="No Supplier Product",
        category="Electronics",
        quantity_on_hand=1,
        avg_daily_demand=10,
        lead_time_days=5,
        safety_stock=10,
        warehouse_type="local",
    )

    db_session.add(inventory)
    db_session.commit()

    seed_sales_history(
        sku_id=sku,
        warehouse_id="WH-M2-NO-SUP",
        daily_quantity=10,
        days=30,
    )

    response = client.post(
        "/api/v1/purchase-orders/draft",
        json={
            "sku_id": sku,
            "warehouse_id": "WH-M2-NO-SUP",
        },
    )

    assert response.status_code == 400


# ============================================================
# MILESTONE 3 — INVENTORY VALUATION
# ============================================================


def add_m3_cost_layer(
    db_session,
    sku_id,
    warehouse_id,
    quantity,
    unit_cost,
):
    inventory = (
        db_session.query(Inventory)
        .filter(
            Inventory.sku_id == sku_id,
            Inventory.warehouse_id == warehouse_id,
        )
        .first()
    )

    layer = InventoryCostLayer(
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        category=inventory.category,
        quantity_received=quantity,
        quantity_remaining=quantity,
        unit_cost=unit_cost,
        received_at=datetime.utcnow(),
    )

    db_session.add(layer)
    db_session.commit()


def test_m3_fifo_inventory_valuation(
    client,
    db_session,
):
    """
    FIFO:

        50 units @ 10
        30 units @ 20

    Current inventory = 80

    Expected:

        (50 * 10) + (30 * 20)
        = 500 + 600
        = 1100
    """

    sku = "SKU-M3-FIFO"

    inventory = Inventory(
        sku_id=sku,
        warehouse_id="WH-M3-FIFO",
        product_name="FIFO Product",
        category="Electronics",
        quantity_on_hand=80,
        avg_daily_demand=5,
        lead_time_days=5,
        safety_stock=10,
        warehouse_type="local",
    )

    db_session.add(inventory)
    db_session.commit()

    add_m3_cost_layer(
        db_session,
        sku,
        "WH-M3-FIFO",
        50,
        10.0,
    )

    add_m3_cost_layer(
        db_session,
        sku,
        "WH-M3-FIFO",
        50,
        20.0,
    )

    response = client.get(
        "/api/v1/reports/inventory-value",
        params={
            "valuation_method": "fifo",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["valuation_method"] == "fifo"
    assert data["total_inventory_value"] == 1100.0


def test_m3_weighted_average_inventory_valuation(
    client,
    db_session,
):
    """
    50 units @ 10
    50 units @ 20

    Weighted average:

        (500 + 1000) / 100
        = 15

    Current inventory = 80

        80 * 15 = 1200
    """

    sku = "SKU-M3-WA"

    inventory = Inventory(
        sku_id=sku,
        warehouse_id="WH-M3-WA",
        product_name="Weighted Average Product",
        category="Electronics",
        quantity_on_hand=80,
        avg_daily_demand=5,
        lead_time_days=5,
        safety_stock=10,
        warehouse_type="local",
    )

    db_session.add(inventory)
    db_session.commit()

    add_m3_cost_layer(
        db_session,
        sku,
        "WH-M3-WA",
        50,
        10.0,
    )

    add_m3_cost_layer(
        db_session,
        sku,
        "WH-M3-WA",
        50,
        20.0,
    )

    response = client.get(
        "/api/v1/reports/inventory-value",
        params={
            "valuation_method": "weighted_average",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["valuation_method"]
        == "weighted_average"
    )

    assert (
        data["total_inventory_value"]
        == 1200.0
    )


def test_m3_inventory_value_grouped_by_warehouse_and_category(
    client,
    db_session,
):
    """
    Verify grouping by:

        warehouse_id + category
    """

    inventory_1 = Inventory(
        sku_id="SKU-M3-GROUP-1",
        warehouse_id="WH-M3-GROUP",
        product_name="Product 1",
        category="Electronics",
        quantity_on_hand=10,
        avg_daily_demand=2,
        lead_time_days=5,
        safety_stock=5,
        warehouse_type="local",
    )

    inventory_2 = Inventory(
        sku_id="SKU-M3-GROUP-2",
        warehouse_id="WH-M3-GROUP",
        product_name="Product 2",
        category="Electronics",
        quantity_on_hand=10,
        avg_daily_demand=2,
        lead_time_days=5,
        safety_stock=5,
        warehouse_type="local",
    )

    db_session.add_all(
        [
            inventory_1,
            inventory_2,
        ]
    )

    db_session.commit()

    add_m3_cost_layer(
        db_session,
        "SKU-M3-GROUP-1",
        "WH-M3-GROUP",
        10,
        100.0,
    )

    add_m3_cost_layer(
        db_session,
        "SKU-M3-GROUP-2",
        "WH-M3-GROUP",
        10,
        200.0,
    )

    response = client.get(
        "/api/v1/reports/inventory-value",
        params={
            "valuation_method": "fifo",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_inventory_value"] == 3000.0

    grouped_item = None

    for item in data["report"]:
        if (
            item["warehouse_id"]
            == "WH-M3-GROUP"
            and item["category"]
            == "Electronics"
        ):
            grouped_item = item
            break

    assert grouped_item is not None
    assert grouped_item["inventory_value"] == 3000.0


def test_m3_zero_inventory_is_excluded_from_report(
    client,
    db_session,
):
    sku = "SKU-M3-ZERO"

    inventory = Inventory(
        sku_id=sku,
        warehouse_id="WH-M3-ZERO",
        product_name="Zero Product",
        category="Electronics",
        quantity_on_hand=0,
        avg_daily_demand=5,
        lead_time_days=5,
        safety_stock=10,
        warehouse_type="local",
    )

    db_session.add(inventory)
    db_session.commit()

    response = client.get(
        "/api/v1/reports/inventory-value",
        params={
            "valuation_method": "fifo",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_inventory_value"] == 0.0

    for item in data["report"]:
        assert not (
            item["warehouse_id"]
            == "WH-M3-ZERO"
        )


def test_m3_invalid_valuation_method_returns_422(
    client,
):
    response = client.get(
        "/api/v1/reports/inventory-value",
        params={
            "valuation_method": "invalid",
        },
    )

    assert response.status_code == 422

