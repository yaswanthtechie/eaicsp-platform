import pytest

from app.core.auth import verify_token
from app.core.config import settings
from app.main import app
from app.models.inventory import Inventory
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from tests.conftest import _as_user, seed_sales_history
from app.services.purchase_order_service import (
    approve_purchase_order,
    determine_approval_status,
    receive_purchase_order,
)


@pytest.mark.parametrize(
    "expected_cost, expected_status",
    [
        (500.0, "approved"),
        (1000.0, "approved"),              # exactly at threshold
        (1000.01, "pending_vp_approval"),  # just above
        (5000.0, "pending_vp_approval"),
    ],
)
def test_determine_approval_status_uses_threshold(
    monkeypatch,
    expected_cost,
    expected_status,
):
    monkeypatch.setattr(
        settings,
        "PO_AUTO_APPROVAL_THRESHOLD",
        1000.0,
    )

    assert (
        determine_approval_status(expected_cost)
        == expected_status
    )


def _seed_reorderable_sku(db_session, unit_cost):
    db_session.add(
        Supplier(
            supplier_id="SUP-APPROVAL",
            sku_id="SKU-APPROVAL",
            supplier_name="Approval Supplier",
            unit_cost=unit_cost,
            lead_time_days=5,
        )
    )
    db_session.add(
        Inventory(
            sku_id="SKU-APPROVAL",
            product_name="Approval Widget",
            warehouse_id="WH-APPROVAL",
            category="Widgets",
            quantity_on_hand=5,
            lead_time_days=5,
            safety_stock=10,
            warehouse_type="local",
        )
    )
    db_session.commit()

    # 10/day demand -> reorder point 60 -> suggests 55 units
    seed_sales_history(
        "SKU-APPROVAL",
        "WH-APPROVAL",
        daily_quantity=10,
    )


def test_small_draft_po_is_auto_approved(client, db_session):
    _seed_reorderable_sku(db_session, unit_cost=1.0)   # 55 x 1 = 55

    response = client.post(
        "/api/v1/inventory/purchase-orders/draft",
        json={"sku_id": "SKU-APPROVAL", "warehouse_id": "WH-APPROVAL"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["approval_status"] == "approved"


def test_large_draft_po_requires_vp_approval(client, db_session):
    _seed_reorderable_sku(db_session, unit_cost=100.0)  # 55 x 100 = 5500

    response = client.post(
        "/api/v1/inventory/purchase-orders/draft",
        json={"sku_id": "SKU-APPROVAL", "warehouse_id": "WH-APPROVAL"},
    )

    assert response.status_code == 201, response.text
    assert (
        response.json()["approval_status"]
        == "pending_vp_approval"
    )


@pytest.mark.parametrize(
    "role",
    ["warehouse_manager", "procurement_manager", "ceo"],
)
def test_only_vp_operations_can_approve(client, db_session, role):
    _seed_reorderable_sku(db_session, unit_cost=100.0)

    po_id = client.post(
        "/api/v1/inventory/purchase-orders/draft",
        json={"sku_id": "SKU-APPROVAL", "warehouse_id": "WH-APPROVAL"},
    ).json()["po_id"]

    app.dependency_overrides[verify_token] = _as_user(role)
    rejected = client.post(
        f"/api/v1/inventory/purchase-orders/{po_id}/approve"
    )
    assert rejected.status_code == 403

    app.dependency_overrides[verify_token] = _as_user("vp_operations")
    approved = client.post(
        f"/api/v1/inventory/purchase-orders/{po_id}/approve"
    )
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "approved"


def test_approving_missing_po_returns_404(client):
    app.dependency_overrides[verify_token] = _as_user("vp_operations")

    response = client.post(
        "/api/v1/inventory/purchase-orders/PO-DOES-NOT-EXIST/approve"
    )

    assert response.status_code == 404


def test_vp_approval_changes_status(db_session):
    po = PurchaseOrder(
        po_id="PO-TEST-VP",
        sku_id="SKU-TEST-003",
        warehouse_id="WH001",
        supplier_id="SUP003",
        quantity=100,
        unit_cost=50.0,
        expected_cost=5000.0,
        status="draft",
        approval_status="pending_vp_approval",
    )

    db_session.add(po)
    db_session.commit()

    approved_po = approve_purchase_order(
        db=db_session,
        po_id="PO-TEST-VP",
    )

    assert approved_po.status == "draft"
    assert approved_po.approval_status == "approved"


def test_already_approved_po_cannot_be_approved_again(
    db_session,
):
    po = PurchaseOrder(
        po_id="PO-TEST-ALREADY",
        sku_id="SKU-TEST-004",
        warehouse_id="WH001",
        supplier_id="SUP004",
        quantity=5,
        unit_cost=50.0,
        expected_cost=250.0,
        status="draft",
        approval_status="approved",
    )

    db_session.add(po)
    db_session.commit()

    try:
        approve_purchase_order(
            db=db_session,
            po_id="PO-TEST-ALREADY",
        )
        assert False, (
            "Expected ValueError for already approved PO"
        )

    except ValueError as exc:
        assert (
            "does not require VP Operations approval"
            in str(exc)
        )


def test_pending_po_cannot_be_received(db_session):
    po = PurchaseOrder(
        po_id="PO-TEST-PENDING",
        sku_id="SKU-TEST-005",
        warehouse_id="WH001",
        supplier_id="SUP005",
        quantity=100,
        unit_cost=50.0,
        expected_cost=5000.0,
        status="draft",
        approval_status="pending_vp_approval",
    )

    db_session.add(po)
    db_session.commit()

    try:
        receive_purchase_order(
            db=db_session,
            po_id="PO-TEST-PENDING",
        )
        assert False, (
            "Expected ValueError for pending approval PO"
        )

    except ValueError as exc:
        assert (
            "requires VP Operations approval"
            in str(exc)
        )