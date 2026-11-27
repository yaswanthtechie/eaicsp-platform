import concurrent.futures
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import settings
from app.models.inventory import Inventory
from app.models.inventory_cost_layer import InventoryCostLayer
from app.models.stock_reservation import StockReservation
from app.services.reservation_service import (
    InsufficientAvailableStockError,
    ReservationExpiredError,
    ReservationNotFoundError,
    ReservationStateError,
    confirm_reservation,
    release_reservation,
    reserve_stock,
)
from tests.conftest import TestingSessionLocal, test_engine


def _seed_inventory(
    db_session,
    *,
    sku_id: str = "SKU-000601",
    warehouse_id: str = "WH-BLR-01",
    quantity_on_hand: int = 100,
    reserved_quantity: int = 0,
) -> Inventory:
    item = Inventory(
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        product_name="Reserved Widget",
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


def _get_inventory(db_session, sku_id: str, warehouse_id: str) -> Inventory:
    db_session.expire_all()
    item = (
        db_session.query(Inventory)
        .filter_by(sku_id=sku_id, warehouse_id=warehouse_id)
        .first()
    )
    assert item is not None
    return item


def test_reserve_stock_success(db_session, monkeypatch):
    monkeypatch.setattr(settings, "RESERVATION_EXPIRATION_SECONDS", 600)
    _seed_inventory(db_session, sku_id="SKU-000601", quantity_on_hand=50)

    before = datetime.now(UTC)
    reservation = reserve_stock(
        db=db_session,
        sku_id="SKU-000601",
        warehouse_id="WH-BLR-01",
        quantity=15,
    )

    assert reservation.reservation_id
    assert reservation.status == "ACTIVE"
    assert reservation.quantity == 15
    assert reservation.expires_at is not None
    expires_utc = (
        reservation.expires_at.replace(tzinfo=UTC)
        if reservation.expires_at.tzinfo is None
        else reservation.expires_at.astimezone(UTC)
    )
    assert expires_utc >= before + timedelta(seconds=590)

    item = _get_inventory(db_session, "SKU-000601", "WH-BLR-01")
    assert item.quantity_on_hand == 50
    assert item.reserved_quantity == 15
    assert item.available_quantity == 35


def test_reserve_stock_insufficient_available(db_session):
    _seed_inventory(
        db_session,
        sku_id="SKU-000602",
        quantity_on_hand=20,
        reserved_quantity=12,
    )

    with pytest.raises(InsufficientAvailableStockError):
        reserve_stock(
            db=db_session,
            sku_id="SKU-000602",
            warehouse_id="WH-BLR-01",
            quantity=9,
        )

    item = _get_inventory(db_session, "SKU-000602", "WH-BLR-01")
    assert item.quantity_on_hand == 20
    assert item.reserved_quantity == 12
    assert item.available_quantity == 8


def test_two_reservations_competing_for_last_units(db_session):
    _seed_inventory(db_session, sku_id="SKU-000603", quantity_on_hand=10)

    first = reserve_stock(
        db=db_session,
        sku_id="SKU-000603",
        warehouse_id="WH-BLR-01",
        quantity=7,
    )
    assert first.status == "ACTIVE"

    with pytest.raises(InsufficientAvailableStockError):
        reserve_stock(
            db=db_session,
            sku_id="SKU-000603",
            warehouse_id="WH-BLR-01",
            quantity=5,
        )

    second = reserve_stock(
        db=db_session,
        sku_id="SKU-000603",
        warehouse_id="WH-BLR-01",
        quantity=3,
    )
    assert second.status == "ACTIVE"

    with pytest.raises(InsufficientAvailableStockError):
        reserve_stock(
            db=db_session,
            sku_id="SKU-000603",
            warehouse_id="WH-BLR-01",
            quantity=1,
        )

    item = _get_inventory(db_session, "SKU-000603", "WH-BLR-01")
    assert item.reserved_quantity == 10
    assert item.available_quantity == 0
    assert item.reserved_quantity <= item.quantity_on_hand


def test_reserve_processes_expired_reservations_before_checking_availability(
    db_session,
):
    _seed_inventory(
        db_session,
        sku_id="SKU-000604",
        quantity_on_hand=10,
        reserved_quantity=8,
    )
    stale = StockReservation(
        sku_id="SKU-000604",
        warehouse_id="WH-BLR-01",
        quantity=8,
        status="ACTIVE",
        expires_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    db_session.add(stale)
    db_session.commit()

    new_res = reserve_stock(
        db=db_session,
        sku_id="SKU-000604",
        warehouse_id="WH-BLR-01",
        quantity=9,
    )

    db_session.expire_all()
    refreshed_stale = (
        db_session.query(StockReservation)
        .filter_by(reservation_id=stale.reservation_id)
        .first()
    )
    assert refreshed_stale is not None
    assert refreshed_stale.status == "EXPIRED"
    assert new_res.status == "ACTIVE"

    item = _get_inventory(db_session, "SKU-000604", "WH-BLR-01")
    assert item.reserved_quantity == 9
    assert item.available_quantity == 1


def test_release_reservation_success_and_double_release_prevented(db_session):
    _seed_inventory(db_session, sku_id="SKU-000605", quantity_on_hand=40)
    res = reserve_stock(
        db=db_session,
        sku_id="SKU-000605",
        warehouse_id="WH-BLR-01",
        quantity=12,
    )

    released = release_reservation(db=db_session, reservation_id=res.reservation_id)
    assert released.status == "RELEASED"

    item = _get_inventory(db_session, "SKU-000605", "WH-BLR-01")
    assert item.quantity_on_hand == 40
    assert item.reserved_quantity == 0
    assert item.available_quantity == 40

    with pytest.raises(ReservationStateError):
        release_reservation(db=db_session, reservation_id=res.reservation_id)

    item_after = _get_inventory(db_session, "SKU-000605", "WH-BLR-01")
    assert item_after.reserved_quantity == 0


def test_confirm_reservation_success_and_double_confirm_prevented(db_session):
    _seed_inventory(db_session, sku_id="SKU-000606", quantity_on_hand=30)
    res = reserve_stock(
        db=db_session,
        sku_id="SKU-000606",
        warehouse_id="WH-BLR-01",
        quantity=10,
    )

    confirmed = confirm_reservation(db=db_session, reservation_id=res.reservation_id)
    assert confirmed.status == "COMMITTED"

    item = _get_inventory(db_session, "SKU-000606", "WH-BLR-01")
    assert item.quantity_on_hand == 20
    assert item.reserved_quantity == 0
    assert item.available_quantity == 20
    assert item.version == 2

    with pytest.raises(ReservationStateError):
        confirm_reservation(db=db_session, reservation_id=res.reservation_id)

    with pytest.raises(ReservationStateError):
        release_reservation(db=db_session, reservation_id=res.reservation_id)

    item_after = _get_inventory(db_session, "SKU-000606", "WH-BLR-01")
    assert item_after.quantity_on_hand == 20
    assert item_after.reserved_quantity == 0
    assert item_after.version == 2


def test_confirm_expired_reservation_rejected(db_session):
    _seed_inventory(
        db_session,
        sku_id="SKU-000607",
        quantity_on_hand=25,
        reserved_quantity=8,
    )
    expired = StockReservation(
        sku_id="SKU-000607",
        warehouse_id="WH-BLR-01",
        quantity=5,
        status="ACTIVE",
        expires_at=datetime.now(UTC) - timedelta(seconds=10),
    )
    db_session.add(expired)
    db_session.commit()

    with pytest.raises(ReservationExpiredError):
        confirm_reservation(db=db_session, reservation_id=expired.reservation_id)

    db_session.expire_all()
    refreshed = (
        db_session.query(StockReservation)
        .filter_by(reservation_id=expired.reservation_id)
        .first()
    )
    assert refreshed is not None
    assert refreshed.status == "EXPIRED"

    item = _get_inventory(db_session, "SKU-000607", "WH-BLR-01")
    assert item.quantity_on_hand == 25
    assert item.reserved_quantity == 3
    assert item.available_quantity == 22
    assert item.version == 1

    # A second confirmation cannot release the same reservation quantity again.
    with pytest.raises(ReservationStateError):
        confirm_reservation(db=db_session, reservation_id=expired.reservation_id)

    item_after = _get_inventory(db_session, "SKU-000607", "WH-BLR-01")
    assert item_after.quantity_on_hand == 25
    assert item_after.reserved_quantity == 3
    assert item_after.version == 1


def test_confirm_consumes_fifo_cost_layers_in_order(db_session):
    _seed_inventory(db_session, sku_id="SKU-000608", quantity_on_hand=20)
    older_time = datetime.now(UTC) - timedelta(days=2)
    newer_time = datetime.now(UTC) - timedelta(days=1)

    layer_old = InventoryCostLayer(
        sku_id="SKU-000608",
        warehouse_id="WH-BLR-01",
        category="Industrial",
        quantity_received=10,
        quantity_remaining=10,
        unit_cost=5.0,
        received_at=older_time,
    )
    layer_new = InventoryCostLayer(
        sku_id="SKU-000608",
        warehouse_id="WH-BLR-01",
        category="Industrial",
        quantity_received=10,
        quantity_remaining=10,
        unit_cost=12.0,
        received_at=newer_time,
    )
    db_session.add_all([layer_old, layer_new])
    db_session.commit()

    res = reserve_stock(
        db=db_session,
        sku_id="SKU-000608",
        warehouse_id="WH-BLR-01",
        quantity=14,
    )
    confirmed = confirm_reservation(db=db_session, reservation_id=res.reservation_id)
    assert confirmed.status == "COMMITTED"

    db_session.expire_all()
    layers = (
        db_session.query(InventoryCostLayer)
        .filter_by(sku_id="SKU-000608", warehouse_id="WH-BLR-01")
        .order_by(InventoryCostLayer.received_at.asc())
        .all()
    )
    assert len(layers) == 2
    assert layers[0].quantity_remaining == 0
    assert layers[1].quantity_remaining == 6

    item = _get_inventory(db_session, "SKU-000608", "WH-BLR-01")
    assert item.quantity_on_hand == 6
    assert item.reserved_quantity == 0
    assert item.available_quantity == 6


def test_release_after_confirm_and_invalid_inputs(db_session):
    _seed_inventory(db_session, sku_id="SKU-000609", quantity_on_hand=15)

    with pytest.raises(ValueError):
        reserve_stock(db_session, "SKU-000609", "WH-BLR-01", quantity=0)

    with pytest.raises(ValueError):
        reserve_stock(db_session, "SKU-000609", "WH-BLR-01", quantity=5, ttl_seconds=0)

    with pytest.raises(ReservationNotFoundError):
        reserve_stock(db_session, "SKU-999999", "WH-BLR-01", quantity=5)

    with pytest.raises(ReservationNotFoundError):
        release_reservation(db_session, "nonexistent-reservation-id")

    with pytest.raises(ReservationNotFoundError):
        confirm_reservation(db_session, "nonexistent-reservation-id")


@pytest.mark.integration
def test_50_parallel_reservations_against_10_units_postgres(db_session):
    """Verify PostgreSQL row locking allows exactly 10 of 50 parallel 1-unit reservations."""
    if test_engine.dialect.name != "postgresql":
        pytest.skip("Integration test requires PostgreSQL")

    sku_id = "SKU-000690"
    warehouse_id = "WH-BLR-01"
    _seed_inventory(
        db_session,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        quantity_on_hand=10,
        reserved_quantity=0,
    )

    def attempt_reserve_one(_worker_idx: int):
        session = TestingSessionLocal()
        try:
            res = reserve_stock(session, sku_id, warehouse_id, quantity=1)
            return ("ok", res.reservation_id)
        except InsufficientAvailableStockError:
            return ("insufficient", None)
        finally:
            session.close()

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(attempt_reserve_one, i) for i in range(50)]
            outcomes = [f.result() for f in futures]

        succeeded = [o for o in outcomes if o[0] == "ok"]
        failed = [o for o in outcomes if o[0] == "insufficient"]
        assert len(succeeded) == 10
        assert len(failed) == 40

        item = _get_inventory(db_session, sku_id, warehouse_id)
        assert item.reserved_quantity == 10
        assert item.available_quantity == 0
        assert item.quantity_on_hand == 10
    finally:
        db_session.rollback()
        db_session.query(StockReservation).filter_by(
            sku_id=sku_id,
            warehouse_id=warehouse_id,
        ).delete()
        db_session.query(Inventory).filter_by(
            sku_id=sku_id,
            warehouse_id=warehouse_id,
        ).delete()
        db_session.commit()
