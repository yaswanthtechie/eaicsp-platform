import concurrent.futures
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect

from app.core.config import settings
from app.models.goods_receipt import GoodsReceipt
from app.models.idempotency import IdempotencyRecord
from app.models.inventory import Inventory
from app.models.outbox import Outbox
from app.models.purchase_order import PurchaseOrder
from app.models.stock_reservation import StockReservation
from app.models.supplier import Supplier
from app.routes.goods_receipts import create_goods_receipt
from app.routes.inventory import (
    confirm_reservation_route,
    create_reservation_route,
    decrement_inventory_route,
    release_reservation_route,
)
from app.routes.purchase_orders import create_purchase_order
from app.schemas.goods_receipt import GoodsReceiptCreate, GoodsReceiptItemCreate
from app.schemas.inventory import (
    BulkUpdateItem,
    InventoryUpdate,
    ReservationCreateRequest,
    ReservationResponse,
)
from app.schemas.purchase_order import PurchaseOrderRequest
from app.services.idempotency_service import execute_idempotent
from app.services.inventory_service import bulk_update_inventory, update_inventory
from app.services.multi_echelon_service import transfer_stock
from app.services.reservation_service import reserve_stock
from tests.conftest import TestingSessionLocal, seed_sales_history, test_engine


def _seed_inventory(
    db_session,
    *,
    sku_id: str = "SKU-000701",
    warehouse_id: str = "WH-BLR-01",
    quantity_on_hand: int = 50,
    reserved_quantity: int = 0,
) -> Inventory:
    item = Inventory(
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        product_name="API Reservation Widget",
        category="Industrial",
        quantity_on_hand=quantity_on_hand,
        reserved_quantity=reserved_quantity,
        lead_time_days=5,
        safety_stock=10,
        warehouse_type="local",
        version=1,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


# ============================================================
# 1. RESERVATION API ROUTE TESTS
# ============================================================


def test_reservation_routes_create_release_confirm_lifecycle(db_session):
    _seed_inventory(db_session, sku_id="SKU-000701", quantity_on_hand=30)

    created = create_reservation_route(
        data=ReservationCreateRequest(
            sku_id="SKU-000701",
            warehouse_id="WH-BLR-01",
            quantity=8,
            ttl_seconds=300,
        ),
        idempotency_key=None,
        db=db_session,
    )
    assert isinstance(created, StockReservation)
    assert created.status == "ACTIVE"
    assert created.quantity == 8

    released = release_reservation_route(
        reservation_id=created.reservation_id,
        db=db_session,
    )
    assert released.status == "RELEASED"

    # Second release -> 409 Conflict
    with pytest.raises(HTTPException) as rel_exc:
        release_reservation_route(reservation_id=created.reservation_id, db=db_session)
    assert rel_exc.value.status_code == 409

    # Create a second reservation and confirm it
    created_two = create_reservation_route(
        data=ReservationCreateRequest(
            sku_id="SKU-000701",
            warehouse_id="WH-BLR-01",
            quantity=10,
        ),
        idempotency_key=None,
        db=db_session,
    )
    assert isinstance(created_two, StockReservation)
    confirmed = confirm_reservation_route(
        reservation_id=created_two.reservation_id,
        db=db_session,
    )
    assert confirmed.status == "COMMITTED"

    # Double confirm -> 409 Conflict
    with pytest.raises(HTTPException) as conf_exc:
        confirm_reservation_route(
            reservation_id=created_two.reservation_id,
            db=db_session,
        )
    assert conf_exc.value.status_code == 409

    db_session.expire_all()
    inv = (
        db_session.query(Inventory)
        .filter_by(sku_id="SKU-000701", warehouse_id="WH-BLR-01")
        .first()
    )
    assert inv is not None
    assert inv.quantity_on_hand == 20
    assert inv.reserved_quantity == 0
    assert inv.available_quantity == 20


def test_reservation_routes_error_cases(db_session):
    _seed_inventory(db_session, sku_id="SKU-000702", quantity_on_hand=5)

    # Positive quantity validation on request schema
    with pytest.raises(ValidationError):
        ReservationCreateRequest(
            sku_id="SKU-000702",
            warehouse_id="WH-BLR-01",
            quantity=0,
        )

    # Missing inventory -> 404
    with pytest.raises(HTTPException) as not_found_exc:
        create_reservation_route(
            data=ReservationCreateRequest(
                sku_id="SKU-999999",
                warehouse_id="WH-BLR-01",
                quantity=1,
            ),
            idempotency_key=None,
            db=db_session,
        )
    assert not_found_exc.value.status_code == 404

    # Insufficient stock -> 409
    with pytest.raises(HTTPException) as insuff_exc:
        create_reservation_route(
            data=ReservationCreateRequest(
                sku_id="SKU-000702",
                warehouse_id="WH-BLR-01",
                quantity=10,
            ),
            idempotency_key=None,
            db=db_session,
        )
    assert insuff_exc.value.status_code == 409

    # Missing reservation on release / confirm -> 404
    with pytest.raises(HTTPException) as rel_404:
        release_reservation_route(reservation_id="missing-res", db=db_session)
    assert rel_404.value.status_code == 404

    with pytest.raises(HTTPException) as conf_404:
        confirm_reservation_route(reservation_id="missing-res", db=db_session)
    assert conf_404.value.status_code == 404


def test_expired_reservation_via_api_releases_once(db_session):
    _seed_inventory(
        db_session,
        sku_id="SKU-000703",
        quantity_on_hand=20,
        reserved_quantity=6,
    )
    expired_res = StockReservation(
        sku_id="SKU-000703",
        warehouse_id="WH-BLR-01",
        quantity=6,
        status="ACTIVE",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    db_session.add(expired_res)
    db_session.commit()

    # Confirming expired reservation -> 409 and persists EXPIRED + releases stock
    with pytest.raises(HTTPException) as exc:
        confirm_reservation_route(
            reservation_id=expired_res.reservation_id,
            db=db_session,
        )
    assert exc.value.status_code == 409

    db_session.expire_all()
    refreshed = (
        db_session.query(StockReservation)
        .filter_by(reservation_id=expired_res.reservation_id)
        .first()
    )
    assert refreshed is not None
    assert refreshed.status == "EXPIRED"

    inv = (
        db_session.query(Inventory)
        .filter_by(sku_id="SKU-000703", warehouse_id="WH-BLR-01")
        .first()
    )
    assert inv is not None
    assert inv.reserved_quantity == 0
    assert inv.quantity_on_hand == 20

    # Subsequent confirm or release cannot decrement reserved_quantity again
    with pytest.raises(HTTPException) as second_conf:
        confirm_reservation_route(
            reservation_id=expired_res.reservation_id,
            db=db_session,
        )
    assert second_conf.value.status_code == 409

    with pytest.raises(HTTPException) as second_rel:
        release_reservation_route(
            reservation_id=expired_res.reservation_id,
            db=db_session,
        )
    assert second_rel.value.status_code == 409


# ============================================================
# 2. IDEMPOTENCY TESTS (RESERVATIONS, PO, GOODS RECEIPT)
# ============================================================


def test_reservation_idempotency_replay_conflict_and_scope_isolation(db_session):
    _seed_inventory(db_session, sku_id="SKU-000704", quantity_on_hand=30)
    req = ReservationCreateRequest(
        sku_id="SKU-000704",
        warehouse_id="WH-BLR-01",
        quantity=5,
    )

    first = create_reservation_route(
        data=req,
        idempotency_key="res-key-001",
        db=db_session,
    )
    assert isinstance(first, StockReservation)

    # Same key + same scope + same body -> replays cached response, no 2nd reservation
    second = create_reservation_route(
        data=req,
        idempotency_key="res-key-001",
        db=db_session,
    )
    assert isinstance(second, JSONResponse)
    assert second.status_code == 201
    second_body = json.loads(bytes(second.body).decode("utf-8"))
    assert second_body["reservation_id"] == first.reservation_id
    assert second_body["quantity"] == 5

    assert (
        db_session.query(StockReservation).filter_by(sku_id="SKU-000704").count() == 1
    )
    db_session.expire_all()
    inv = (
        db_session.query(Inventory)
        .filter_by(sku_id="SKU-000704", warehouse_id="WH-BLR-01")
        .first()
    )
    assert inv is not None
    assert inv.reserved_quantity == 5

    # Same key + same scope + different body -> 409 Conflict
    with pytest.raises(HTTPException) as conflict_exc:
        create_reservation_route(
            data=ReservationCreateRequest(
                sku_id="SKU-000704",
                warehouse_id="WH-BLR-01",
                quantity=7,
            ),
            idempotency_key="res-key-001",
            db=db_session,
        )
    assert conflict_exc.value.status_code == 409


def test_purchase_order_idempotency_replay_and_cross_scope_isolation(db_session):
    _seed_inventory(db_session, sku_id="SKU-000705", quantity_on_hand=5)
    db_session.add(
        Supplier(
            supplier_id="SUP-00705",
            supplier_name="Idempotent Supplier",
            sku_id="SKU-000705",
            unit_cost=40.0,
            lead_time_days=5,
        )
    )
    db_session.commit()
    seed_sales_history("SKU-000705", "WH-BLR-01", daily_quantity=5, days=30)

    # First reserve with shared key "shared-key-01" to test scope isolation
    res = create_reservation_route(
        data=ReservationCreateRequest(
            sku_id="SKU-000705",
            warehouse_id="WH-BLR-01",
            quantity=2,
        ),
        idempotency_key="shared-key-01",
        db=db_session,
    )
    assert isinstance(res, StockReservation)

    # Same key on PO endpoint must NOT replay the reservation response
    po_req = PurchaseOrderRequest(sku_id="SKU-000705", warehouse_id="WH-BLR-01")
    first_po = create_purchase_order(
        data=po_req,
        idempotency_key="shared-key-01",
        db=db_session,
        auth={"user_id": 1, "role": "procurement_manager"},
    )
    assert isinstance(first_po, PurchaseOrder)

    second_po = create_purchase_order(
        data=po_req,
        idempotency_key="shared-key-01",
        db=db_session,
        auth={"user_id": 1, "role": "procurement_manager"},
    )
    assert isinstance(second_po, JSONResponse)
    assert second_po.status_code == 201
    second_body = json.loads(bytes(second_po.body).decode("utf-8"))
    assert second_body["po_id"] == first_po.po_id
    assert db_session.query(PurchaseOrder).filter_by(sku_id="SKU-000705").count() == 1
    assert (
        db_session.query(Outbox)
        .filter_by(event_type="inventory.po.drafted", aggregate_id=first_po.po_id)
        .count()
        == 1
    )


def test_goods_receipt_idempotency_replay_creates_one_receipt(db_session):
    _seed_inventory(db_session, sku_id="SKU-000706", quantity_on_hand=10)
    db_session.add(
        PurchaseOrder(
            po_id="PO-2026-000706",
            sku_id="SKU-000706",
            warehouse_id="WH-BLR-01",
            supplier_id="SUP-00706",
            quantity=20,
            unit_cost=50.0,
            expected_cost=1000.0,
            status="acknowledged",
            approval_status="approved",
        )
    )
    db_session.commit()

    gr_req = GoodsReceiptCreate(
        po_id="PO-2026-000706",
        warehouse_id="WH-BLR-01",
        items=[
            GoodsReceiptItemCreate(
                sku_id="SKU-000706",
                quantity_received=10,
                unit_cost=50.0,
            )
        ],
    )
    first_gr = create_goods_receipt(
        data=gr_req,
        idempotency_key="gr-key-001",
        db=db_session,
        auth={"user_id": 42, "role": "warehouse_manager"},
    )
    assert isinstance(first_gr, GoodsReceipt)

    second_gr = create_goods_receipt(
        data=gr_req,
        idempotency_key="gr-key-001",
        db=db_session,
        auth={"user_id": 42, "role": "warehouse_manager"},
    )
    assert isinstance(second_gr, JSONResponse)
    assert second_gr.status_code == 201
    second_body = json.loads(bytes(second_gr.body).decode("utf-8"))
    assert second_body["receipt_id"] == first_gr.receipt_id

    assert db_session.query(GoodsReceipt).filter_by(po_id="PO-2026-000706").count() == 1
    db_session.expire_all()
    inv = (
        db_session.query(Inventory)
        .filter_by(sku_id="SKU-000706", warehouse_id="WH-BLR-01")
        .first()
    )
    assert inv is not None
    assert inv.quantity_on_hand == 20  # incremented once (10 + 10)


def test_failed_operation_does_not_cache_idempotency_and_expired_key_reusable(
    db_session, monkeypatch
):
    _seed_inventory(db_session, sku_id="SKU-000707", quantity_on_hand=3)

    # 1. Failed request (insufficient stock) must NOT leave a cached response
    with pytest.raises(HTTPException) as fail_exc:
        create_reservation_route(
            data=ReservationCreateRequest(
                sku_id="SKU-000707",
                warehouse_id="WH-BLR-01",
                quantity=5,
            ),
            idempotency_key="retry-after-fail",
            db=db_session,
        )
    assert fail_exc.value.status_code == 409
    assert (
        db_session.query(IdempotencyRecord)
        .filter_by(idempotency_key="retry-after-fail")
        .count()
        == 0
    )

    # Restock and retry with same key -> succeeds
    inv = (
        db_session.query(Inventory)
        .filter_by(sku_id="SKU-000707", warehouse_id="WH-BLR-01")
        .first()
    )
    assert inv is not None
    inv.quantity_on_hand = 20
    db_session.commit()

    monkeypatch.setattr(settings, "IDEMPOTENCY_RETENTION_SECONDS", 60)
    ok = create_reservation_route(
        data=ReservationCreateRequest(
            sku_id="SKU-000707",
            warehouse_id="WH-BLR-01",
            quantity=5,
        ),
        idempotency_key="retry-after-fail",
        db=db_session,
    )
    assert isinstance(ok, StockReservation)

    # 2. Expire the idempotency record and reuse the key with a new request body
    rec = (
        db_session.query(IdempotencyRecord)
        .filter_by(idempotency_key="retry-after-fail")
        .first()
    )
    assert rec is not None
    rec.expires_at = datetime.now(UTC) - timedelta(seconds=5)
    db_session.commit()

    reused = create_reservation_route(
        data=ReservationCreateRequest(
            sku_id="SKU-000707",
            warehouse_id="WH-BLR-01",
            quantity=4,
        ),
        idempotency_key="retry-after-fail",
        db=db_session,
    )
    assert isinstance(reused, StockReservation)
    assert reused.reservation_id != ok.reservation_id
    assert reused.quantity == 4


def test_purchase_order_idempotency_409_no_key_and_expired_reuse(db_session):
    _seed_inventory(db_session, sku_id="SKU-000708", quantity_on_hand=5)
    _seed_inventory(db_session, sku_id="SKU-000709", quantity_on_hand=5)
    for sku, sup in (("SKU-000708", "SUP-00708"), ("SKU-000709", "SUP-00709")):
        db_session.add(
            Supplier(
                supplier_id=sup,
                supplier_name=f"Supplier {sup}",
                sku_id=sku,
                unit_cost=25.0,
                lead_time_days=4,
            )
        )
        seed_sales_history(sku, "WH-BLR-01", daily_quantity=5, days=30)
    db_session.commit()

    # 1. No Idempotency-Key preserves existing behavior (creates distinct POs)
    po_no_key_1 = create_purchase_order(
        data=PurchaseOrderRequest(sku_id="SKU-000708", warehouse_id="WH-BLR-01"),
        idempotency_key=None,
        db=db_session,
        auth={"user_id": 1, "role": "procurement_manager"},
    )
    po_no_key_2 = create_purchase_order(
        data=PurchaseOrderRequest(sku_id="SKU-000708", warehouse_id="WH-BLR-01"),
        idempotency_key=None,
        db=db_session,
        auth={"user_id": 1, "role": "procurement_manager"},
    )
    assert isinstance(po_no_key_1, PurchaseOrder)
    assert isinstance(po_no_key_2, PurchaseOrder)
    assert po_no_key_1.po_id != po_no_key_2.po_id

    # 2. Same key + different body -> 409 Conflict
    po_with_key = create_purchase_order(
        data=PurchaseOrderRequest(sku_id="SKU-000708", warehouse_id="WH-BLR-01"),
        idempotency_key="po-key-conflict",
        db=db_session,
        auth={"user_id": 1, "role": "procurement_manager"},
    )
    assert isinstance(po_with_key, PurchaseOrder)

    with pytest.raises(HTTPException) as conflict_exc:
        create_purchase_order(
            data=PurchaseOrderRequest(sku_id="SKU-000709", warehouse_id="WH-BLR-01"),
            idempotency_key="po-key-conflict",
            db=db_session,
            auth={"user_id": 1, "role": "procurement_manager"},
        )
    assert conflict_exc.value.status_code == 409

    # 3. Expired key can be reused
    rec = (
        db_session.query(IdempotencyRecord)
        .filter_by(idempotency_key="po-key-conflict")
        .first()
    )
    assert rec is not None
    rec.expires_at = datetime.now(UTC) - timedelta(seconds=5)
    db_session.commit()

    po_reused = create_purchase_order(
        data=PurchaseOrderRequest(sku_id="SKU-000709", warehouse_id="WH-BLR-01"),
        idempotency_key="po-key-conflict",
        db=db_session,
        auth={"user_id": 1, "role": "procurement_manager"},
    )
    assert isinstance(po_reused, PurchaseOrder)
    assert po_reused.po_id != po_with_key.po_id


def test_goods_receipt_idempotency_409_no_key_and_expired_reuse(db_session):
    _seed_inventory(db_session, sku_id="SKU-000710", quantity_on_hand=10)
    db_session.add(
        PurchaseOrder(
            po_id="PO-2026-000710",
            sku_id="SKU-000710",
            warehouse_id="WH-BLR-01",
            supplier_id="SUP-00710",
            quantity=30,
            unit_cost=50.0,
            expected_cost=1500.0,
            status="acknowledged",
            approval_status="approved",
        )
    )
    db_session.commit()

    # 1. No Idempotency-Key creates distinct partial receipts
    gr1 = create_goods_receipt(
        data=GoodsReceiptCreate(
            po_id="PO-2026-000710",
            warehouse_id="WH-BLR-01",
            items=[GoodsReceiptItemCreate(sku_id="SKU-000710", quantity_received=5)],
        ),
        idempotency_key=None,
        db=db_session,
        auth={"user_id": 42, "role": "warehouse_manager"},
    )
    gr2 = create_goods_receipt(
        data=GoodsReceiptCreate(
            po_id="PO-2026-000710",
            warehouse_id="WH-BLR-01",
            items=[GoodsReceiptItemCreate(sku_id="SKU-000710", quantity_received=5)],
        ),
        idempotency_key=None,
        db=db_session,
        auth={"user_id": 42, "role": "warehouse_manager"},
    )
    assert isinstance(gr1, GoodsReceipt)
    assert isinstance(gr2, GoodsReceipt)
    assert gr1.receipt_id != gr2.receipt_id

    # 2. Same key + different body -> 409 Conflict
    gr_keyed = create_goods_receipt(
        data=GoodsReceiptCreate(
            po_id="PO-2026-000710",
            warehouse_id="WH-BLR-01",
            items=[GoodsReceiptItemCreate(sku_id="SKU-000710", quantity_received=5)],
        ),
        idempotency_key="gr-key-conflict",
        db=db_session,
        auth={"user_id": 42, "role": "warehouse_manager"},
    )
    assert isinstance(gr_keyed, GoodsReceipt)

    with pytest.raises(HTTPException) as conflict_exc:
        create_goods_receipt(
            data=GoodsReceiptCreate(
                po_id="PO-2026-000710",
                warehouse_id="WH-BLR-01",
                items=[
                    GoodsReceiptItemCreate(sku_id="SKU-000710", quantity_received=6)
                ],
            ),
            idempotency_key="gr-key-conflict",
            db=db_session,
            auth={"user_id": 42, "role": "warehouse_manager"},
        )
    assert conflict_exc.value.status_code == 409

    # 3. Expired key can be reused
    rec = (
        db_session.query(IdempotencyRecord)
        .filter_by(idempotency_key="gr-key-conflict")
        .first()
    )
    assert rec is not None
    rec.expires_at = datetime.now(UTC) - timedelta(seconds=5)
    db_session.commit()

    gr_reused = create_goods_receipt(
        data=GoodsReceiptCreate(
            po_id="PO-2026-000710",
            warehouse_id="WH-BLR-01",
            items=[GoodsReceiptItemCreate(sku_id="SKU-000710", quantity_received=5)],
        ),
        idempotency_key="gr-key-conflict",
        db=db_session,
        auth={"user_id": 42, "role": "warehouse_manager"},
    )
    assert isinstance(gr_reused, GoodsReceipt)
    assert gr_reused.receipt_id != gr_keyed.receipt_id


def test_reservation_without_idempotency_key_creates_distinct_records(db_session):
    _seed_inventory(db_session, sku_id="SKU-000711", quantity_on_hand=20)
    req = ReservationCreateRequest(
        sku_id="SKU-000711",
        warehouse_id="WH-BLR-01",
        quantity=4,
    )
    r1 = create_reservation_route(data=req, idempotency_key=None, db=db_session)
    r2 = create_reservation_route(data=req, idempotency_key=None, db=db_session)
    assert isinstance(r1, StockReservation)
    assert isinstance(r2, StockReservation)
    assert r1.reservation_id != r2.reservation_id


def test_decrement_and_stock_mutations_cannot_consume_reserved_stock(db_session):
    _seed_inventory(db_session, sku_id="SKU-000712", quantity_on_hand=20)
    _seed_inventory(
        db_session,
        sku_id="SKU-000712",
        warehouse_id="WH-BOM-01",
        quantity_on_hand=10,
    )
    reserve_stock(db_session, "SKU-000712", "WH-BLR-01", quantity=15)

    # 1. /decrement cannot consume the 15 reserved units (only 5 available)
    with pytest.raises(HTTPException) as dec_exc:
        decrement_inventory_route(
            sku_id="SKU-000712",
            warehouse_id="WH-BLR-01",
            quantity=10,
            db=db_session,
        )
    assert dec_exc.value.status_code == 409

    # Decrementing within available (5) succeeds
    dec_ok = decrement_inventory_route(
        sku_id="SKU-000712",
        warehouse_id="WH-BLR-01",
        quantity=5,
        db=db_session,
    )
    assert dec_ok["quantity_on_hand"] == 15

    # 2. bulk_update_inventory cannot reduce below reserved_quantity (15)
    with pytest.raises(ValueError, match="Insufficient available stock"):
        bulk_update_inventory(
            updates=[
                BulkUpdateItem(
                    sku_id="SKU-000712",
                    warehouse_id="WH-BLR-01",
                    quantity_delta=-1,
                )
            ],
            db=db_session,
        )

    # 3. update_inventory cannot reduce quantity_on_hand below reserved_quantity
    with pytest.raises(HTTPException) as upd_exc:
        update_inventory(
            db=db_session,
            sku_id="SKU-000712",
            warehouse_id="WH-BLR-01",
            inventory=InventoryUpdate(quantity_on_hand=14, version=2),
        )
    assert upd_exc.value.status_code == 409

    # 4. transfer_stock cannot transfer reserved units out of source
    with pytest.raises(ValueError, match="Insufficient available stock"):
        transfer_stock(
            db=db_session,
            sku_id="SKU-000712",
            source_warehouse_id="WH-BLR-01",
            destination_warehouse_id="WH-BOM-01",
            quantity=1,
        )
    db_session.rollback()

    # 5. Stale expired reservation is lazily released on decrement
    active_res = (
        db_session.query(StockReservation)
        .filter_by(sku_id="SKU-000712", warehouse_id="WH-BLR-01", status="ACTIVE")
        .first()
    )
    assert active_res is not None
    active_res.expires_at = datetime.now(UTC) - timedelta(seconds=5)
    db_session.commit()

    dec_after_expiry = decrement_inventory_route(
        sku_id="SKU-000712",
        warehouse_id="WH-BLR-01",
        quantity=10,
        db=db_session,
    )
    assert dec_after_expiry["quantity_on_hand"] == 5
    db_session.expire_all()
    inv = (
        db_session.query(Inventory)
        .filter_by(sku_id="SKU-000712", warehouse_id="WH-BLR-01")
        .first()
    )
    assert inv is not None
    assert inv.reserved_quantity == 0
    assert inv.available_quantity == 5


def test_migration_011_idempotency_records_upgrade_and_downgrade(tmp_path):
    service_dir = Path(__file__).resolve().parents[1]
    db_file = tmp_path / "test_idempotency_migration.db"
    db_url = f"sqlite:///{db_file}"

    alembic_cfg = Config(str(service_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(service_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(alembic_cfg, "head")
    engine = create_engine(db_url)
    inspector = inspect(engine)

    assert "idempotency_records" in set(inspector.get_table_names())
    cols = {c["name"] for c in inspector.get_columns("idempotency_records")}
    assert {
        "id",
        "idempotency_key",
        "scope",
        "request_hash",
        "status",
        "response_status_code",
        "response_body",
        "created_at",
        "expires_at",
    }.issubset(cols)
    uniques = {
        uc["name"] for uc in inspector.get_unique_constraints("idempotency_records")
    }
    assert "uq_idempotency_key_scope" in uniques

    command.downgrade(alembic_cfg, "010_stock_reservations")
    inspector_after = inspect(engine)
    assert "idempotency_records" not in set(inspector_after.get_table_names())
    engine.dispose()


@pytest.mark.integration
def test_concurrent_same_idempotency_key_postgres(db_session):
    """Verify 10 concurrent identical idempotent reservation requests create only 1 reservation."""
    if test_engine.dialect.name != "postgresql":
        pytest.skip("Integration test requires PostgreSQL")

    sku_id = "SKU-000790"
    warehouse_id = "WH-BLR-01"
    _seed_inventory(
        db_session,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        quantity_on_hand=20,
    )

    req = ReservationCreateRequest(
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        quantity=5,
    )

    def send_request(_idx: int):
        session = TestingSessionLocal()
        try:
            res = execute_idempotent(
                db=session,
                idempotency_key="concurrent-idem-key-01",
                scope="POST:/api/v1/inventory/reservations",
                request_payload=req,
                success_status_code=201,
                action=lambda: reserve_stock(
                    db=session,
                    sku_id=req.sku_id,
                    warehouse_id=req.warehouse_id,
                    quantity=req.quantity,
                    commit=False,
                ),
                serialize=lambda r: ReservationResponse.model_validate(r),
            )
            if isinstance(res, JSONResponse):
                return json.loads(bytes(res.body).decode("utf-8"))["reservation_id"]
            return res.reservation_id
        finally:
            session.close()

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            ids = [
                f.result()
                for f in [executor.submit(send_request, i) for i in range(10)]
            ]

        assert len(set(ids)) == 1
        assert (
            db_session.query(StockReservation)
            .filter_by(sku_id=sku_id, warehouse_id=warehouse_id)
            .count()
            == 1
        )
        db_session.expire_all()
        inv = (
            db_session.query(Inventory)
            .filter_by(sku_id=sku_id, warehouse_id=warehouse_id)
            .first()
        )
        assert inv is not None
        assert inv.reserved_quantity == 5
    finally:
        db_session.rollback()
        db_session.query(IdempotencyRecord).filter_by(
            idempotency_key="concurrent-idem-key-01"
        ).delete()
        db_session.query(StockReservation).filter_by(
            sku_id=sku_id, warehouse_id=warehouse_id
        ).delete()
        db_session.query(Inventory).filter_by(
            sku_id=sku_id, warehouse_id=warehouse_id
        ).delete()
        db_session.commit()
