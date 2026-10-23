import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator

from app.core.auth import verify_token
from app.models.outbox import Outbox
from app.services.outbox_relay import OutboxRelay
from tests.fakes import InMemoryKafkaPublisher
from app.schemas.events import InventoryPOApprovedEvent
from app.main import app
from app.models.inventory import Inventory
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from tests.conftest import _as_user, seed_sales_history
from app.services.purchase_order_service import (
    approve_purchase_order,
    receive_purchase_order,
)


def _seed_reorderable_sku(db_session, unit_cost):
    db_session.add(
        Supplier(
            supplier_id="SUP-00901",
            sku_id="SKU-000901",
            supplier_name="Approval Supplier",
            unit_cost=unit_cost,
            lead_time_days=5,
        )
    )
    db_session.add(
        Inventory(
            sku_id="SKU-000901",
            product_name="Approval Widget",
            warehouse_id="WH-BLR-01",
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
        "SKU-000901",
        "WH-BLR-01",
        daily_quantity=10,
    )


def test_small_draft_po_is_auto_approved(client, db_session):
    _seed_reorderable_sku(db_session, unit_cost=1.0)   # 55 x 1 = 55

    response = client.post(
        "/api/v1/inventory/purchase-orders/draft",
        json={"sku_id": "SKU-000901", "warehouse_id": "WH-BLR-01"},
    )

    assert response.status_code == 201, response.text
    po_id = response.json()["po_id"]
    assert response.json()["approval_status"] == "pending_vp_approval"

    app.dependency_overrides[verify_token] = _as_user("procurement_manager")
    approved = client.post(f"/api/v1/inventory/purchase-orders/{po_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "approved"


def test_large_draft_po_requires_vp_approval(client, db_session):
    _seed_reorderable_sku(db_session, unit_cost=100.0)  # 55 x 100 = 5500

    response = client.post(
        "/api/v1/inventory/purchase-orders/draft",
        json={"sku_id": "SKU-000901", "warehouse_id": "WH-BLR-01"},
    )

    assert response.status_code == 201, response.text
    assert (
        response.json()["approval_status"]
        == "pending_vp_approval"
    )


@pytest.mark.parametrize(
    "role",
    ["warehouse_manager", "analyst", "ceo"],
)
def test_approval_requires_procurement_manager(client, db_session, role):
    _seed_reorderable_sku(db_session, unit_cost=100.0)

    po_id = client.post(
        "/api/v1/inventory/purchase-orders/draft",
        json={"sku_id": "SKU-000901", "warehouse_id": "WH-BLR-01"},
    ).json()["po_id"]

    app.dependency_overrides[verify_token] = _as_user(role)
    rejected = client.post(
        f"/api/v1/inventory/purchase-orders/{po_id}/approve"
    )
    assert rejected.status_code == 403

    app.dependency_overrides[verify_token] = _as_user("procurement_manager")
    approved = client.post(
        f"/api/v1/inventory/purchase-orders/{po_id}/approve"
    )
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "approved"


def test_approving_missing_po_returns_404(client):
    app.dependency_overrides[verify_token] = _as_user("procurement_manager")

    response = client.post(
        "/api/v1/inventory/purchase-orders/PO-2026-999999/approve"
    )

    assert response.status_code == 404


def test_approve_without_user_id_returns_401(client, db_session):
    async def _no_user_id():
        return {"valid": True, "role": "procurement_manager", "permissions": []}

    app.dependency_overrides[verify_token] = _no_user_id
    response = client.post("/api/v1/inventory/purchase-orders/PO-2026-999999/approve")
    assert response.status_code == 401


def test_vp_approval_changes_status(db_session):
    po = PurchaseOrder(
        po_id="PO-2026-900001",
        sku_id="SKU-000903",
        warehouse_id="WH-BLR-01",
        supplier_id="SUP-00901",
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
        po_id="PO-2026-900001",
        approved_by="7",
    )

    assert approved_po.status == "draft"
    assert approved_po.approval_status == "approved"


def test_already_approved_po_cannot_be_approved_again(
    db_session,
):
    po = PurchaseOrder(
        po_id="PO-2026-900002",
        sku_id="SKU-000904",
        warehouse_id="WH-BLR-01",
        supplier_id="SUP-00901",
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
            po_id="PO-2026-900002",
            approved_by="7",
        )
        assert False, (
            "Expected ValueError for already approved PO"
        )

    except ValueError as exc:
        assert (
            "is not awaiting approval"
            in str(exc)
        )


def test_pending_po_cannot_be_received(db_session):
    po = PurchaseOrder(
        po_id="PO-2026-900003",
        sku_id="SKU-000905",
        warehouse_id="WH-BLR-01",
        supplier_id="SUP-00901",
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
            po_id="PO-2026-900003",
        )
        assert False, (
            "Expected ValueError for pending approval PO"
        )

    except ValueError as exc:
        assert (
            "requires VP Operations approval"
            in str(exc)
        )


def test_approve_po_publishes_inventory_po_approved_event(client, db_session):
    """
    Done-when:
    1. Approval requires procurement_manager
    2. Event written through outbox, matching the contract exactly
    3. Test: approve, then the outbox relay publishes exactly one event
    """
    app.dependency_overrides[verify_token] = lambda: {
        "valid": True,
        "role": "procurement_manager",
        "user_id": 7,
        "email": "pm@example.com",
        "permissions": ["supplier:read", "supplier:write"],
    }

    # 1. Seed canonical PO requiring approval
    po = PurchaseOrder(
        po_id="PO-2026-000123",
        sku_id="SKU-000123",
        warehouse_id="WH-BLR-01",
        supplier_id="SUP-00045",
        quantity=100,
        unit_cost=450.0,
        expected_cost=45000.0,
        status="draft",
        approval_status="pending_vp_approval",
    )
    db_session.add(po)
    db_session.commit()

    # 2. Approve via API endpoint
    response = client.post("/api/v1/inventory/purchase-orders/PO-2026-000123/approve")
    assert response.status_code == 200, response.text
    assert response.json()["approval_status"] == "approved"

    # 3. Verify atomic outbox entry written with status PENDING
    outbox_entry = (
        db_session.query(Outbox)
        .filter(
            Outbox.aggregate_id == "PO-2026-000123",
            Outbox.event_type == "inventory.po.approved",
        )
        .first()
    )
    assert outbox_entry is not None, "Outbox event must be recorded during PO approval"
    assert outbox_entry.status == "PENDING"
    assert outbox_entry.retry_count == 0

    # 4. Run Outbox Relay to publish to Kafka
    fake_publisher = InMemoryKafkaPublisher()
    relay = OutboxRelay(publisher=fake_publisher)
    published_count, failed_count = relay.relay_pending_events(db=db_session)

    # Done-when: Outbox relay publishes exactly ONE event
    assert published_count == 1
    assert failed_count == 0
    assert len(fake_publisher.published_messages) == 1

    msg = fake_publisher.published_messages[0]
    assert msg["topic"] == "inventory.po.approved"
    assert msg["key"] == "PO-2026-000123"

    # 5. Verify published message matches contract schema strictly
    repo_root = Path(__file__).resolve().parents[3]
    schema_path = repo_root / "contracts" / "events" / "inventory.po.approved.v1.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    envelope = json.loads(msg["value"])
    Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(envelope)

    # 6. Verify with strict Pydantic model
    event = InventoryPOApprovedEvent.model_validate(envelope)
    assert event.event_type == "inventory.po.approved"
    assert event.event_version == 1
    assert event.producer == "inventory-service"
    assert event.payload.approved_by == "7"
    assert event.payload.approval_status == "approved"
    assert event.payload.total_amount == 45000.0
    assert len(event.payload.lines) == 1
    assert event.payload.lines[0].sku_id == "SKU-000123"
    assert event.payload.lines[0].quantity == 100

    # 7. Verify outbox entry state transitions to PUBLISHED
    db_session.refresh(outbox_entry)
    assert outbox_entry.status == "PUBLISHED"
    assert outbox_entry.published_at is not None
