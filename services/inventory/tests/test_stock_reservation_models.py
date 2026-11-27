from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.models.inventory import Inventory
from app.models.stock_reservation import RESERVATION_STATUSES, StockReservation


def _seed_inventory(
    db_session,
    *,
    sku_id: str = "SKU-000501",
    warehouse_id: str = "WH-BLR-01",
    quantity_on_hand: int = 100,
    **kwargs,
) -> Inventory:
    item = Inventory(
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        product_name="Reservation Test Item",
        category="Industrial",
        quantity_on_hand=quantity_on_hand,
        lead_time_days=5,
        safety_stock=10,
        warehouse_type="local",
        **kwargs,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


def test_inventory_default_reserved_quantity_and_available_quantity(db_session):
    item = _seed_inventory(db_session, quantity_on_hand=75)

    assert item.reserved_quantity == 0
    assert item.available_quantity == 75

    item.reserved_quantity = 20
    db_session.commit()
    db_session.refresh(item)

    assert item.reserved_quantity == 20
    assert item.available_quantity == 55


def test_inventory_negative_reserved_quantity_rejected(db_session):
    _seed_inventory(db_session, sku_id="SKU-000502", reserved_quantity=0)

    item = (
        db_session.query(Inventory)
        .filter_by(sku_id="SKU-000502", warehouse_id="WH-BLR-01")
        .first()
    )
    assert item is not None
    item.reserved_quantity = -1

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_stock_reservation_model_creation(db_session):
    item = _seed_inventory(db_session, sku_id="SKU-000503", quantity_on_hand=50)
    expires_at = datetime.now(UTC) + timedelta(minutes=30)

    reservation = StockReservation(
        sku_id=item.sku_id,
        warehouse_id=item.warehouse_id,
        quantity=15,
        expires_at=expires_at,
    )
    db_session.add(reservation)
    db_session.commit()
    db_session.refresh(reservation)

    assert reservation.reservation_id
    assert reservation.sku_id == item.sku_id
    assert reservation.warehouse_id == item.warehouse_id
    assert reservation.quantity == 15
    assert reservation.status == "ACTIVE"
    assert reservation.expires_at is not None
    assert reservation.created_at is not None
    assert reservation.updated_at is not None
    assert len(item.reservations) == 1
    assert item.reservations[0].reservation_id == reservation.reservation_id


@pytest.mark.parametrize("bad_quantity", [0, -1, -25])
def test_stock_reservation_requires_positive_quantity(db_session, bad_quantity):
    item = _seed_inventory(db_session, sku_id="SKU-000504")

    reservation = StockReservation(
        sku_id=item.sku_id,
        warehouse_id=item.warehouse_id,
        quantity=bad_quantity,
        status="ACTIVE",
    )
    db_session.add(reservation)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("status", RESERVATION_STATUSES)
def test_stock_reservation_valid_statuses(db_session, status):
    item = _seed_inventory(
        db_session,
        sku_id="SKU-000505",
        warehouse_id=f"WH-{status[:3]}-01",
    )

    reservation = StockReservation(
        sku_id=item.sku_id,
        warehouse_id=item.warehouse_id,
        quantity=5,
        status=status,
    )
    db_session.add(reservation)
    db_session.commit()
    db_session.refresh(reservation)

    assert reservation.status == status


def test_stock_reservation_invalid_status_rejected(db_session):
    item = _seed_inventory(db_session, sku_id="SKU-000506")

    reservation = StockReservation(
        sku_id=item.sku_id,
        warehouse_id=item.warehouse_id,
        quantity=5,
        status="PENDING",
    )
    db_session.add(reservation)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_migration_010_upgrade_and_downgrade(tmp_path):
    service_dir = Path(__file__).resolve().parents[1]
    db_file = tmp_path / "test_reservation_migration.db"
    db_url = f"sqlite:///{db_file}"

    alembic_cfg = Config(str(service_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(service_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Upgrade to 009 first and insert an existing inventory row
    command.upgrade(alembic_cfg, "009_snapshot_po_history")
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO inventory "
                "(sku_id, warehouse_id, product_name, category, quantity_on_hand, "
                "avg_daily_demand, lead_time_days, safety_stock, warehouse_type, version) "
                "VALUES ('SKU-000510', 'WH-BLR-01', 'Pre-existing', 'Hardware', 40, 2.0, 4, 10, 'local', 1)"
            )
        )

    # Upgrade to 010 / head
    command.upgrade(alembic_cfg, "head")
    inspector = inspect(engine)

    inv_columns = {c["name"]: c for c in inspector.get_columns("inventory")}
    assert "reserved_quantity" in inv_columns
    assert inv_columns["reserved_quantity"]["nullable"] is False

    inv_checks = {ck.get("name") for ck in inspector.get_check_constraints("inventory")}
    assert "ck_inventory_reserved_quantity_non_negative" in inv_checks

    with engine.connect() as conn:
        reserved = conn.execute(
            text(
                "SELECT reserved_quantity FROM inventory "
                "WHERE sku_id = 'SKU-000510' AND warehouse_id = 'WH-BLR-01'"
            )
        ).scalar_one()
    assert reserved == 0

    assert "stock_reservations" in set(inspector.get_table_names())
    res_cols = {c["name"] for c in inspector.get_columns("stock_reservations")}
    assert {
        "reservation_id",
        "sku_id",
        "warehouse_id",
        "quantity",
        "status",
        "expires_at",
        "created_at",
        "updated_at",
    }.issubset(res_cols)

    res_indexes = {idx["name"] for idx in inspector.get_indexes("stock_reservations")}
    assert {
        "ix_stock_reservations_sku_warehouse_status",
        "ix_stock_reservations_status_expires_at",
    }.issubset(res_indexes)

    res_checks = {
        ck.get("name") for ck in inspector.get_check_constraints("stock_reservations")
    }
    assert {
        "ck_stock_reservations_quantity_positive",
        "ck_stock_reservations_status",
    }.issubset(res_checks)

    res_fks = inspector.get_foreign_keys("stock_reservations")
    assert any(
        fk["referred_table"] == "inventory"
        and fk["constrained_columns"] == ["sku_id", "warehouse_id"]
        and fk["referred_columns"] == ["sku_id", "warehouse_id"]
        for fk in res_fks
    )

    # Downgrade back to 009
    command.downgrade(alembic_cfg, "009_snapshot_po_history")
    inspector_after = inspect(engine)
    assert "stock_reservations" not in set(inspector_after.get_table_names())
    inv_cols_after = {c["name"] for c in inspector_after.get_columns("inventory")}
    assert "reserved_quantity" not in inv_cols_after
    engine.dispose()
