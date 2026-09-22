"""
Regression tests for the inventory service review fixes.

These tests cover:
- route registration
- authentication protection
- warehouse hierarchy cycle detection
- self-parent validation
- FIFO cost-layer consumption
- cost-layer movement during transfers
- decrementing inventory created through the public API
- opening-stock valuation
- uncosted stock movement
- automatic draft PO generation after decrement
"""

from datetime import datetime, timedelta

import pytest

from app.models.inventory import Inventory
from app.models.inventory_cost_layer import InventoryCostLayer
from app.services.multi_echelon_service import fulfill_shortage
from app.services.valuation_service import (
    calculate_fifo_value,
    consume_cost_layers,
)
from tests.conftest import seed_sales_history


def _inventory(**overrides):
    data = dict(
        sku_id="SKU-REG",
        warehouse_id="WH-A",
        product_name="Regression Widget",
        category="Widgets",
        quantity_on_hand=0,
        avg_daily_demand=1.0,
        lead_time_days=1,
        safety_stock=0,
        warehouse_type="local",
        parent_warehouse_id=None,
        version=1,
    )

    data.update(overrides)

    return Inventory(**data)


def test_app_imports_and_exposes_routes():
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if hasattr(route, "methods")
    }

    assert "/api/v1/inventory" in paths
    assert "/api/v1/inventory/purchase-orders/draft" in paths
    assert "/api/v1/inventory/reports/inventory-value" in paths


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/inventory"),
        ("post", "/api/v1/inventory"),
        ("get", "/api/v1/inventory/low-stock"),
        ("get", "/api/v1/inventory/reorder-plan"),
        ("post", "/api/v1/inventory/decrement"),
        ("post", "/api/v1/inventory/multi-echelon/fulfill"),
        ("get", "/api/v1/inventory/SKU1/WH1"),
        ("put", "/api/v1/inventory/SKU1/WH1"),
        ("delete", "/api/v1/inventory/SKU1/WH1"),
        ("get", "/api/v1/inventory/reports/inventory-value"),
        ("post", "/api/v1/inventory/purchase-orders/draft"),
    ],
)
def test_endpoints_reject_missing_token(
    client_raw,
    method,
    path,
):
    response = client_raw.request(
        method.upper(),
        path,
        json={},
    )

    assert response.status_code == 401, (
        f"{method.upper()} {path} "
        f"answered {response.status_code} without a token"
    )


def test_parent_cycle_is_rejected_instead_of_hanging(
    db_session,
):
    db_session.add_all(
        [
            _inventory(
                warehouse_id="WH-A",
                parent_warehouse_id="WH-B",
            ),
            _inventory(
                warehouse_id="WH-B",
                parent_warehouse_id="WH-A",
            ),
        ]
    )

    db_session.commit()

    with pytest.raises(ValueError, match="cycle"):
        fulfill_shortage(
            db=db_session,
            sku_id="SKU-REG",
            warehouse_id="WH-A",
            required_quantity=5,
        )


def test_warehouse_cannot_be_its_own_parent(client):
    response = client.post(
        "/api/v1/inventory",
        json={
            "sku_id": "SKU-SELF",
            "product_name": "Self Parent",
            "warehouse_id": "WH-SELF",
            "category": "Widgets",
            "quantity_on_hand": 5,
            "lead_time_days": 2,
            "safety_stock": 1,
            "warehouse_type": "local",
            "parent_warehouse_id": "WH-SELF",
        },
    )

    assert response.status_code == 400


def test_fifo_value_after_stock_leaves(db_session):
    received = datetime(2026, 1, 1)

    db_session.add(
        _inventory(
            warehouse_id="WH-VAL",
            quantity_on_hand=20,
        )
    )

    db_session.add(
        InventoryCostLayer(
            sku_id="SKU-REG",
            warehouse_id="WH-VAL",
            category="Widgets",
            quantity_received=10,
            quantity_remaining=10,
            unit_cost=5.0,
            received_at=received,
        )
    )

    db_session.add(
        InventoryCostLayer(
            sku_id="SKU-REG",
            warehouse_id="WH-VAL",
            category="Widgets",
            quantity_received=10,
            quantity_remaining=10,
            unit_cost=10.0,
            received_at=received + timedelta(days=30),
        )
    )

    db_session.commit()

    assert (
        calculate_fifo_value(
            db_session,
            "SKU-REG",
            "WH-VAL",
        )
        == 150.0
    )

    item = (
        db_session.query(Inventory)
        .filter(
            Inventory.warehouse_id == "WH-VAL"
        )
        .first()
    )

    item.quantity_on_hand = 10

    consume_cost_layers(
        db_session,
        "SKU-REG",
        "WH-VAL",
        10,
    )

    db_session.commit()

    assert (
        calculate_fifo_value(
            db_session,
            "SKU-REG",
            "WH-VAL",
        )
        == 100.0
    )


def test_transfer_moves_cost_layers_to_destination(
    db_session,
):
    db_session.add(
        _inventory(
            warehouse_id="WH-SRC",
            quantity_on_hand=10,
        )
    )

    db_session.add(
        _inventory(
            warehouse_id="WH-DST",
            quantity_on_hand=0,
            parent_warehouse_id="WH-SRC",
        )
    )

    db_session.add(
        InventoryCostLayer(
            sku_id="SKU-REG",
            warehouse_id="WH-SRC",
            category="Widgets",
            quantity_received=10,
            quantity_remaining=10,
            unit_cost=7.0,
            received_at=datetime(2026, 1, 1),
        )
    )

    db_session.commit()

    fulfill_shortage(
        db=db_session,
        sku_id="SKU-REG",
        warehouse_id="WH-DST",
        required_quantity=4,
    )

    assert (
        calculate_fifo_value(
            db_session,
            "SKU-REG",
            "WH-SRC",
        )
        == 42.0
    )

    assert (
        calculate_fifo_value(
            db_session,
            "SKU-REG",
            "WH-DST",
        )
        == 28.0
    )


# =========================================================
# REVIEW FIX 1
# Decrement must work for inventory created through the API.
#
# Cost layers are a valuation concern. A record with no cost
# history must still be able to move stock.
# =========================================================

def test_decrement_works_for_inventory_created_via_api(client):
    """Create then decrement, using only the public API."""

    created = client.post(
        "/api/v1/inventory",
        json={
            "sku_id": "SKU-DEC",
            "product_name": "Decrement Widget",
            "warehouse_id": "WH-DEC",
            "category": "Widgets",
            "quantity_on_hand": 50,
            "lead_time_days": 2,
            "safety_stock": 1,
            "warehouse_type": "local",
        },
    )

    assert created.status_code == 201, created.text

    response = client.post(
        "/api/v1/inventory/decrement",
        params={
            "sku_id": "SKU-DEC",
            "warehouse_id": "WH-DEC",
            "quantity": 5,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["quantity_on_hand"] == 45


# =========================================================
# REVIEW FIX 1
# Opening stock with unit_cost gets a valuation cost layer.
# =========================================================

def test_opening_unit_cost_gives_new_inventory_a_cost_basis(
    client,
):
    """
    Stock created with a unit_cost is valued immediately,
    and valuation follows the stock as it leaves.
    """

    created = client.post(
        "/api/v1/inventory",
        json={
            "sku_id": "SKU-COST",
            "product_name": "Costed Widget",
            "warehouse_id": "WH-COST",
            "category": "Widgets",
            "quantity_on_hand": 40,
            "lead_time_days": 2,
            "safety_stock": 1,
            "warehouse_type": "local",
            "unit_cost": 12.5,
        },
    )

    assert created.status_code == 201, created.text

    report = client.get(
        "/api/v1/inventory/reports/inventory-value"
    )

    assert report.status_code == 200, report.text
    assert report.json()["total_inventory_value"] == 500.0

    response = client.post(
        "/api/v1/inventory/decrement",
        params={
            "sku_id": "SKU-COST",
            "warehouse_id": "WH-COST",
            "quantity": 10,
        },
    )

    assert response.status_code == 200, response.text

    report = client.get(
        "/api/v1/inventory/reports/inventory-value"
    )

    assert report.status_code == 200, report.text

    # 30 units remaining at 12.50
    assert report.json()["total_inventory_value"] == 375.0


# =========================================================
# REVIEW FIX 1
# Uncosted stock must still move physically.
# =========================================================

def test_uncosted_stock_moves_but_is_not_valued(client):
    """
    Without a unit_cost there is no cost basis, so the stock
    is not included in the valuation report. The stock must
    still move.
    """

    created = client.post(
        "/api/v1/inventory",
        json={
            "sku_id": "SKU-NOCOST",
            "product_name": "Uncosted Widget",
            "warehouse_id": "WH-NOCOST",
            "category": "Widgets",
            "quantity_on_hand": 20,
            "lead_time_days": 2,
            "safety_stock": 1,
            "warehouse_type": "local",
        },
    )

    assert created.status_code == 201, created.text

    response = client.post(
        "/api/v1/inventory/decrement",
        params={
            "sku_id": "SKU-NOCOST",
            "warehouse_id": "WH-NOCOST",
            "quantity": 8,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["quantity_on_hand"] == 12

    report = client.get(
        "/api/v1/inventory/reports/inventory-value"
    )

    assert report.status_code == 200, report.text
    assert report.json()["total_inventory_value"] == 0.0


# =========================================================
# REVIEW FIX 2
# Decrementing below ROP must trigger draft PO generation.
# =========================================================

def test_decrement_below_reorder_point_generates_draft_po(
    client,
    db_session,
):
    """
    A sale can push inventory below the reorder point, so the
    automatic draft PO logic must run after decrement.
    """

    from app.models.purchase_order import PurchaseOrder
    from app.models.supplier import Supplier

    sku = "SKU-DEC-PO"
    warehouse = "WH-DEC-PO"

    db_session.add(
        Supplier(
            supplier_id="SUP-DEC",
            sku_id=sku,
            supplier_name="Decrement Supplier",
            unit_cost=25.0,
            lead_time_days=5,
        )
    )

    db_session.commit()

    seed_sales_history(
        sku,
        warehouse,
        daily_quantity=10,
    )

    created = client.post(
        "/api/v1/inventory",
        json={
            "sku_id": sku,
            "product_name": "Decrement PO Widget",
            "warehouse_id": warehouse,
            "category": "Widgets",
            "quantity_on_hand": 500,
            "lead_time_days": 5,
            "safety_stock": 10,
            "warehouse_type": "local",
            "unit_cost": 25.0,
        },
    )

    assert created.status_code == 201, created.text

    assert (
        db_session.query(PurchaseOrder)
        .filter(
            PurchaseOrder.sku_id == sku
        )
        .count()
        == 0
    )

    response = client.post(
        "/api/v1/inventory/decrement",
        params={
            "sku_id": sku,
            "warehouse_id": warehouse,
            "quantity": 495,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["quantity_on_hand"] == 5

    purchase_orders = (
        db_session.query(PurchaseOrder)
        .filter(
            PurchaseOrder.sku_id == sku
        )
        .all()
    )

    assert len(purchase_orders) == 1, (
        "Decrementing below the reorder point should "
        "auto-generate a draft PO"
    )