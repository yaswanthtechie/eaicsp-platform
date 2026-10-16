"""
Tests for Seed Loader and Canonical Master Data (Round 15: Flow A)
"""

import csv
import re
import pytest
from pathlib import Path

from app.models.product import Product
from app.models.warehouse import Warehouse
from app.models.inventory import Inventory
from scripts.load_seed import (
    run_loader,
    load_warehouses,
    load_products,
    load_opening_stock,
    SKU_RE,
    WH_RE,
    SUP_RE,
    resolve_seed_directory,
)


def test_resolve_seed_directory():
    seed_dir = resolve_seed_directory()
    assert seed_dir.exists()
    assert (seed_dir / "skus.csv").exists()
    assert (seed_dir / "warehouses.csv").exists()
    assert (seed_dir / "opening_stock.csv").exists()


def test_seed_loader_populates_canonical_data(db_session):
    result = run_loader(wipe=True, db=db_session)


    assert result["warehouses_loaded"] >= 6
    assert result["products_loaded"] >= 10
    assert result["opening_stock_loaded"] >= 10

    # Verify warehouses in database
    warehouses = db_session.query(Warehouse).all()
    assert len(warehouses) >= 6
    for wh in warehouses:
        assert WH_RE.match(wh.warehouse_id), f"Non-canonical warehouse ID: {wh.warehouse_id}"
        assert wh.name
        assert wh.city
        assert wh.capacity_units > 0

    # Verify products in database
    products = db_session.query(Product).all()
    assert len(products) >= 10
    for prod in products:
        assert SKU_RE.match(prod.sku_id), f"Non-canonical SKU ID: {prod.sku_id}"
        assert prod.name
        assert prod.category
        assert prod.unit_cost > 0
        if prod.supplier_id:
            assert SUP_RE.match(prod.supplier_id), f"Non-canonical Supplier ID: {prod.supplier_id}"

    # Verify opening stock inventory in database
    inventories = db_session.query(Inventory).all()
    assert len(inventories) >= 10
    for inv in inventories:
        assert SKU_RE.match(inv.sku_id), f"Non-canonical SKU ID: {inv.sku_id}"
        assert WH_RE.match(inv.warehouse_id), f"Non-canonical Warehouse ID: {inv.warehouse_id}"
        assert inv.quantity_on_hand >= 0
        assert inv.product_name


def test_seed_loader_rejects_non_canonical_warehouse_id(tmp_path, db_session):
    bad_wh_csv = tmp_path / "warehouses.csv"
    with open(bad_wh_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["warehouse_id", "name", "city", "state", "capacity_units", "demand_weight"])
        writer.writerow(["WH001", "Old Format DC", "City", "State", "100000", "1.0"])  # Non-canonical!

    with pytest.raises(ValueError, match="Invalid non-canonical warehouse_id"):
        load_warehouses(db=db_session, seed_dir=tmp_path, wipe=False)


def test_seed_loader_rejects_non_canonical_sku_id(tmp_path, db_session):
    bad_sku_csv = tmp_path / "skus.csv"
    with open(bad_sku_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sku_id", "name", "category", "pack_size", "unit_price", "unit_cost", "abc_class", "supplier_id"])
        writer.writerow(["SKU001", "Legacy Item", "Electronics", "1 pc", "100.0", "50.0", "A", "SUP-00001"])  # Non-canonical!

    with pytest.raises(ValueError, match="Invalid non-canonical sku_id"):
        load_products(db=db_session, seed_dir=tmp_path, wipe=False)


def test_seed_loader_idempotent(db_session):
    # Running multiple times must succeed without primary key collisions
    res1 = run_loader(wipe=False, db=db_session)
    res2 = run_loader(wipe=False, db=db_session)

    assert res1["warehouses_loaded"] == res2["warehouses_loaded"]
    assert res1["products_loaded"] == res2["products_loaded"]

