from app.models.purchase_order import PurchaseOrder
from app.services.purchase_order_service import (
    approve_purchase_order,
    receive_purchase_order,
)


def test_small_po_is_auto_approved(db_session):
    po = PurchaseOrder(
        po_id="PO-TEST-SMALL",
        sku_id="SKU-TEST-001",
        warehouse_id="WH001",
        supplier_id="SUP001",
        quantity=10,
        unit_cost=50.0,
        expected_cost=500.0,
        status="draft",
        approval_status="approved",
    )

    db_session.add(po)
    db_session.commit()

    saved_po = (
        db_session.query(PurchaseOrder)
        .filter(
            PurchaseOrder.po_id == "PO-TEST-SMALL"
        )
        .first()
    )

    assert saved_po is not None
    assert saved_po.status == "draft"
    assert saved_po.approval_status == "approved"


def test_large_po_requires_vp_approval(db_session):
    po = PurchaseOrder(
        po_id="PO-TEST-LARGE",
        sku_id="SKU-TEST-002",
        warehouse_id="WH001",
        supplier_id="SUP002",
        quantity=100,
        unit_cost=50.0,
        expected_cost=5000.0,
        status="draft",
        approval_status="pending_vp_approval",
    )

    db_session.add(po)
    db_session.commit()

    saved_po = (
        db_session.query(PurchaseOrder)
        .filter(
            PurchaseOrder.po_id == "PO-TEST-LARGE"
        )
        .first()
    )

    assert saved_po is not None
    assert saved_po.status == "draft"
    assert (
        saved_po.approval_status
        == "pending_vp_approval"
    )


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