"""
Tests for Seed Loader and Canonical Master Data (Round 15: Flow A)
"""

import csv
import pytest

from app.models.inventory import Inventory
from app.models.inventory_cost_layer import InventoryCostLayer
from app.models.product import Product
from app.models.sales_history import SalesHistory
from app.models.warehouse import Warehouse
from app.services.purchase_order_service import select_supplier
from scripts.load_seed import (
    SKU_RE,
    WH_RE,
    load_products,
    load_warehouses,
    resolve_seed_directory,
    run_loader,
)


def _write(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


@pytest.fixture
def seed_dir(tmp_path):
    """A tiny, internally consistent seed: 2 suppliers, 3 SKUs (SUP-00045 supplies two)."""
    _write(
        tmp_path / "warehouses.csv",
        ["warehouse_id", "name", "city", "state", "lat", "lng", "capacity_units", "demand_weight"],
        [
            ["WH-BLR-01", "Bengaluru DC", "Bengaluru", "Karnataka", "12.97", "77.59", "120000", "1.25"],
            ["WH-DEL-01", "Delhi DC", "New Delhi", "Delhi", "28.61", "77.20", "90000", "1.0"],
        ],
    )
    _write(
        tmp_path / "suppliers.csv",
        ["supplier_id", "name", "country", "lead_time_days"],
        [
            ["SUP-00045", "Acme Fasteners", "India", "12"],
            ["SUP-00007", "Alpha Sanctions Corp", "Russia", "32"],
        ],
    )
    _write(
        tmp_path / "skus.csv",
        ["sku_id", "name", "category", "pack_size", "unit_price", "unit_cost", "abc_class", "supplier_id"],
        [
            ["SKU-000001", "Bolt", "Hardware", "Box of 100", "100.0", "60.0", "A", "SUP-00045"],
            ["SKU-000002", "Nut", "Hardware", "Box of 100", "80.0", "45.0", "B", "SUP-00045"],
            ["SKU-000003", "Chair", "Furniture", "1 pc", "900.0", "600.0", "C", "SUP-00007"],
        ],
    )
    _write(
        tmp_path / "sales_daily.csv",
        ["date", "sku_id", "warehouse_id", "quantity_sold", "unit_price"],
        [
            ["2026-10-13", "SKU-000001", "WH-BLR-01", "10", "100.0"],
            ["2026-10-14", "SKU-000001", "WH-BLR-01", "20", "100.0"],
            ["2026-10-14", "SKU-000002", "WH-DEL-01", "4", "80.0"],
        ],
    )
    _write(
        tmp_path / "current_stock.csv",
        ["snapshot_date", "sku_id", "warehouse_id", "quantity_on_hand"],
        [
            ["2026-10-14", "SKU-000001", "WH-BLR-01", "85"],
            ["2026-10-14", "SKU-000002", "WH-DEL-01", "40"],
            ["2026-10-14", "SKU-000003", "WH-DEL-01", "0"],
        ],
    )
    return tmp_path


def test_resolve_seed_directory_fails_loudly_when_files_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="current_stock.csv"):
        resolve_seed_directory(str(tmp_path))


def test_seed_loader_populates_canonical_data(seed_dir, db_session):
    result = run_loader(seed_dir_path=str(seed_dir), wipe=True, db=db_session)
    assert result["warehouses_loaded"] == 2
    assert result["products_loaded"] == 3
    assert result["suppliers_loaded"] == 2
    assert result["sales_history_loaded"] == 3
    assert result["current_stock_loaded"] == 3

    for wh in db_session.query(Warehouse):
        assert WH_RE.match(wh.warehouse_id)
    for prod in db_session.query(Product):
        assert SKU_RE.match(prod.sku_id)

    bolt = db_session.query(Inventory).filter_by(sku_id="SKU-000001", warehouse_id="WH-BLR-01").one()
    assert bolt.quantity_on_hand == 85
    assert bolt.lead_time_days == 12  # from suppliers.csv, not invented
    assert bolt.avg_daily_demand == 15.0  # (10 + 20) / 2 observed days up to the snapshot date
    assert bolt.warehouse_type == "central"

    nut = db_session.query(Inventory).filter_by(sku_id="SKU-000002", warehouse_id="WH-DEL-01").one()
    assert nut.parent_warehouse_id == "WH-BLR-01"


def test_every_seeded_sku_can_find_its_supplier(seed_dir, db_session):
    run_loader(seed_dir_path=str(seed_dir), wipe=True, db=db_session)
    for inv in db_session.query(Inventory):
        product = db_session.get(Product, inv.sku_id)
        supplier = select_supplier(db=db_session, sku_id=inv.sku_id)
        assert supplier.supplier_id == product.supplier_id
        assert supplier.unit_cost == product.unit_cost


def test_seed_loader_is_idempotent(seed_dir, db_session):
    run_loader(seed_dir_path=str(seed_dir), wipe=True, db=db_session)
    counts = (
        db_session.query(Inventory).count(),
        db_session.query(InventoryCostLayer).count(),
        db_session.query(SalesHistory).count(),
    )
    run_loader(seed_dir_path=str(seed_dir), db=db_session)
    assert (
        db_session.query(Inventory).count(),
        db_session.query(InventoryCostLayer).count(),
        db_session.query(SalesHistory).count(),
    ) == counts
    assert counts[1] == 2  # one layer per SKU/warehouse with stock; none for the 0-qty row


def test_failed_load_changes_nothing(seed_dir, db_session):
    run_loader(seed_dir_path=str(seed_dir), wipe=True, db=db_session)
    with open(seed_dir / "skus.csv", "a", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(["SKU001", "Legacy", "Hardware", "", "1", "1", "A", "SUP-00045"])  # noncanonical-ok

    with pytest.raises(ValueError, match="Invalid non-canonical sku_id"):
        run_loader(seed_dir_path=str(seed_dir), wipe=True, db=db_session)

    assert db_session.query(Product).count() == 3
    assert db_session.query(Inventory).count() == 3


def test_seed_loader_rejects_non_canonical_warehouse_id(tmp_path, db_session):
    _write(
        tmp_path / "warehouses.csv",
        ["warehouse_id", "name", "city", "state", "capacity_units", "demand_weight"],
        [["WH001", "Old Format DC", "City", "State", "100000", "1.0"]],  # noncanonical-ok
    )
    with pytest.raises(ValueError, match="Invalid non-canonical warehouse_id"):
        load_warehouses(db=db_session, seed_dir=tmp_path)


def test_seed_loader_rejects_non_canonical_sku_id(tmp_path, db_session):
    _write(
        tmp_path / "skus.csv",
        ["sku_id", "name", "category", "pack_size", "unit_price", "unit_cost", "abc_class", "supplier_id"],
        [["SKU001", "Legacy Item", "Electronics", "1 pc", "100.0", "50.0", "A", "SUP-00001"]],  # noncanonical-ok
    )
    with pytest.raises(ValueError, match="Invalid non-canonical sku_id"):
        load_products(db=db_session, seed_dir=tmp_path)
