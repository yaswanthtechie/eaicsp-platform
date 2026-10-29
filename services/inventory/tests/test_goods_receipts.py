from datetime import UTC, datetime
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator

from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.inventory import Inventory
from app.models.inventory_cost_layer import InventoryCostLayer
from app.models.outbox import Outbox
from app.models.purchase_order import PurchaseOrder
from app.schemas.goods_receipt import GoodsReceiptCreate, GoodsReceiptItemCreate
from app.services.goods_receipt_service import record_goods_receipt
from tests.conftest import _as_user

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "contracts" / "events" / "inventory.goods.received.v1.json"


def _validate_event_schema(data):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(data)


@pytest.fixture
def seed_inventory_and_po(db_session):
    inv = Inventory(
        sku_id="SKU-000123",
        warehouse_id="WH-BLR-01",
        product_name="Flow B Widget",
        category="Electronics",
        quantity_on_hand=100,
        lead_time_days=7,
        safety_stock=20,
        version=1,
    )
    po = PurchaseOrder(
        po_id="PO-2026-000123",
        sku_id="SKU-000123",
        warehouse_id="WH-BLR-01",
        supplier_id="SUP-00045",
        quantity=50,
        unit_cost=300.0,
        expected_cost=15000.0,
        status="acknowledged",
        approval_status="approved",
    )
    db_session.add_all([inv, po])
    db_session.commit()
    return inv, po


def test_full_goods_receipt(client, db_session, seed_inventory_and_po):
    """
    Test a full goods receipt:
    - On-hand stock increases by received quantity.
    - Cost layer is appended to inventory_cost_layers.
    - GoodsReceipt and GoodsReceiptItem records exist.
    - PO status transitions to 'received'.
    - Outbox event 'inventory.goods.received' validates against Draft-2020-12 contract schema.
    """
    payload = {
        "po_id": "PO-2026-000123",
        "warehouse_id": "WH-BLR-01",
        "items": [
            {
                "sku_id": "SKU-000123",
                "quantity_received": 50,
                "unit_cost": 300.0,
            }
        ],
        "notes": "Full delivery verified at BLR gate 3",
    }

    resp = client.post("/api/v1/inventory/goods-receipts", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert data["receipt_id"].startswith(f"GR-{datetime.now(UTC).year}-")
    assert data["po_id"] == "PO-2026-000123"
    assert data["supplier_id"] == "SUP-00045"
    assert data["warehouse_id"] == "WH-BLR-01"
    assert data["status"] == "received"
    assert data["notes"] == "Full delivery verified at BLR gate 3"
    assert len(data["items"]) == 1
    assert data["items"][0]["sku_id"] == "SKU-000123"
    assert data["items"][0]["quantity_received"] == 50

    # 1. Check database state
    inv = db_session.query(Inventory).filter(Inventory.sku_id == "SKU-000123").first()
    assert inv.quantity_on_hand == 150  # 100 + 50

    po = db_session.query(PurchaseOrder).filter(PurchaseOrder.po_id == "PO-2026-000123").first()
    assert po.status == "received"

    # Cost layer exists
    cost_layer = (
        db_session.query(InventoryCostLayer)
        .filter(
            InventoryCostLayer.sku_id == "SKU-000123",
            InventoryCostLayer.warehouse_id == "WH-BLR-01",
        )
        .first()
    )
    assert cost_layer is not None
    assert cost_layer.quantity_received == 50
    assert cost_layer.unit_cost == 300.0

    # Goods receipt row exists
    gr = db_session.query(GoodsReceipt).filter(GoodsReceipt.receipt_id == data["receipt_id"]).first()
    assert gr is not None
    assert len(gr.items) == 1

    # 2. Check Outbox event validates against JSON schema contract
    outbox = (
        db_session.query(Outbox)
        .filter(
            Outbox.event_type == "inventory.goods.received",
            Outbox.aggregate_id == gr.receipt_id,
        )
        .first()
    )
    assert outbox is not None
    event_dict = json.loads(outbox.payload)
    _validate_event_schema(event_dict)
    assert event_dict["payload"]["receipt_id"] == gr.receipt_id
    assert event_dict["payload"]["po_id"] == "PO-2026-000123"
    assert event_dict["payload"]["supplier_id"] == "SUP-00045"
    assert event_dict["payload"]["status"] == "received"
    assert len(event_dict["payload"]["items"]) == 1


def test_partial_goods_receipt(client, db_session, seed_inventory_and_po):
    """
    Test partial goods receipt:
    - Receiving less than PO quantity transitions PO to 'partially_received'.
    - Receiving remaining balance transitions PO to 'received'.
    """
    # 1. First partial receipt: 20 out of 50
    resp1 = client.post(
        "/api/v1/inventory/goods-receipts",
        json={
            "po_id": "PO-2026-000123",
            "warehouse_id": "WH-BLR-01",
            "items": [
                {
                    "sku_id": "SKU-000123",
                    "quantity_received": 20,
                }
            ],
            "notes": "Partial batch 1",
        },
    )
    assert resp1.status_code == 201

    po = db_session.query(PurchaseOrder).filter(PurchaseOrder.po_id == "PO-2026-000123").first()
    assert po.status == "partially_received"

    inv = db_session.query(Inventory).filter(Inventory.sku_id == "SKU-000123").first()
    assert inv.quantity_on_hand == 120  # 100 + 20

    # 2. Second receipt: remaining 30 out of 50
    resp2 = client.post(
        "/api/v1/inventory/goods-receipts",
        json={
            "po_id": "PO-2026-000123",
            "warehouse_id": "WH-BLR-01",
            "items": [
                {
                    "sku_id": "SKU-000123",
                    "quantity_received": 30,
                }
            ],
            "notes": "Partial batch 2 (final)",
        },
    )
    assert resp2.status_code == 201

    db_session.refresh(po)
    assert po.status == "received"

    db_session.refresh(inv)
    assert inv.quantity_on_hand == 150  # 120 + 30


def test_sku_not_on_po_returns_400(client, db_session, seed_inventory_and_po):
    """
    A SKU that isn't on the PO must return 400 Bad Request,
    and make NO changes to stock or PO status.
    """
    payload = {
        "po_id": "PO-2026-000123",
        "warehouse_id": "WH-BLR-01",
        "items": [
            {
                "sku_id": "SKU-999999",  # not on PO
                "quantity_received": 10,
            }
        ],
    }
    resp = client.post("/api/v1/inventory/goods-receipts", json=payload)
    assert resp.status_code == 400
    assert "does not belong to purchase order" in resp.json()["detail"].lower()

    # Verify no state changes
    inv = db_session.query(Inventory).filter(Inventory.sku_id == "SKU-000123").first()
    assert inv.quantity_on_hand == 100

    po = db_session.query(PurchaseOrder).filter(PurchaseOrder.po_id == "PO-2026-000123").first()
    assert po.status == "acknowledged"

    # No goods receipt was saved
    assert db_session.query(GoodsReceipt).count() == 0


def test_unapproved_po_returns_400(client, db_session):
    """A PO that is not approved must return 400, nothing changes."""
    inv = Inventory(
        sku_id="SKU-000123",
        warehouse_id="WH-BLR-01",
        product_name="Flow B Widget",
        category="Electronics",
        quantity_on_hand=100,
        lead_time_days=7,
        safety_stock=20,
    )
    po = PurchaseOrder(
        po_id="PO-2026-000124",
        sku_id="SKU-000123",
        warehouse_id="WH-BLR-01",
        supplier_id="SUP-00045",
        quantity=50,
        unit_cost=300.0,
        expected_cost=15000.0,
        status="draft",
        approval_status="pending_vp_approval",  # unapproved
    )
    db_session.add_all([inv, po])
    db_session.commit()

    resp = client.post(
        "/api/v1/inventory/goods-receipts",
        json={
            "po_id": "PO-2026-000124",
            "warehouse_id": "WH-BLR-01",
            "items": [{"sku_id": "SKU-000123", "quantity_received": 50}],
        },
    )
    assert resp.status_code == 400
    assert "approved" in resp.json()["detail"].lower()

    db_session.refresh(inv)
    assert inv.quantity_on_hand == 100


def test_po_on_hold_returns_400(client, db_session):
    """A PO that is on hold must return 400, nothing changes."""
    inv = Inventory(
        sku_id="SKU-000123",
        warehouse_id="WH-BLR-01",
        product_name="Flow B Widget",
        category="Electronics",
        quantity_on_hand=100,
        lead_time_days=7,
        safety_stock=20,
    )
    po = PurchaseOrder(
        po_id="PO-2026-000125",
        sku_id="SKU-000123",
        warehouse_id="WH-BLR-01",
        supplier_id="SUP-00045",
        quantity=50,
        unit_cost=300.0,
        expected_cost=15000.0,
        status="on_hold",
        approval_status="approved",
        hold_reason="Compliance sanctions screening in progress",
    )
    db_session.add_all([inv, po])
    db_session.commit()

    resp = client.post(
        "/api/v1/inventory/goods-receipts",
        json={
            "po_id": "PO-2026-000125",
            "warehouse_id": "WH-BLR-01",
            "items": [{"sku_id": "SKU-000123", "quantity_received": 50}],
        },
    )
    assert resp.status_code == 400
    assert "on hold" in resp.json()["detail"].lower()

    db_session.refresh(inv)
    assert inv.quantity_on_hand == 100


def test_analyst_role_returns_403(client_raw, db_session, seed_inventory_and_po):
    """An analyst role calling goods-receipts must return 403 Forbidden."""
    from app.main import app
    from app.core.auth import verify_token
    from fastapi.testclient import TestClient

    app.dependency_overrides[verify_token] = _as_user("analyst")
    try:
        with TestClient(app) as test_client:
            resp = test_client.post(
                "/api/v1/inventory/goods-receipts",
                json={
                    "po_id": "PO-2026-000123",
                    "warehouse_id": "WH-BLR-01",
                    "items": [{"sku_id": "SKU-000123", "quantity_received": 50}],
                },
            )
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_legacy_po_receive_delegation(client, db_session, seed_inventory_and_po):
    """
    Deprecated POST /api/v1/inventory/purchase-orders/{po_id}/receive
    delegates to record_goods_receipt with full quantity and returns 200.
    """
    resp = client.post("/api/v1/inventory/purchase-orders/PO-2026-000123/receive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "received"

    # Database reflections
    inv = db_session.query(Inventory).filter(Inventory.sku_id == "SKU-000123").first()
    assert inv.quantity_on_hand == 150

    po = db_session.query(PurchaseOrder).filter(PurchaseOrder.po_id == "PO-2026-000123").first()
    assert po.status == "received"

    # Goods receipt row was created
    gr = db_session.query(GoodsReceipt).filter(GoodsReceipt.po_id == "PO-2026-000123").first()
    assert gr is not None
    assert gr.status == "received"


def test_over_receipt_returns_400(client, db_session, seed_inventory_and_po):
    resp = client.post(
        "/api/v1/inventory/goods-receipts",
        json={
            "po_id": "PO-2026-000123",
            "warehouse_id": "WH-BLR-01",
            "items": [{"sku_id": "SKU-000123", "quantity_received": 51}],
        },
    )
    assert resp.status_code == 400
    assert "exceeds" in resp.json()["detail"]
    inv = db_session.query(Inventory).filter_by(sku_id="SKU-000123", warehouse_id="WH-BLR-01").one()
    assert inv.quantity_on_hand == 100  # unchanged


def test_legacy_receive_requires_warehouse_manager(client, db_session, seed_inventory_and_po):
    from app.main import app
    from app.core.auth import verify_token
    app.dependency_overrides[verify_token] = _as_user("analyst")
    resp = client.post("/api/v1/inventory/purchase-orders/PO-2026-000123/receive")
    assert resp.status_code == 403

def test_acknowledged_po_counts_as_open(db_session, seed_inventory_and_po):
    from app.services.purchase_order_service import find_existing_draft_po

    existing = find_existing_draft_po(db_session, "SKU-000123", "WH-BLR-01")
    assert existing is not None
    assert existing.po_id == "PO-2026-000123"

