#!/usr/bin/env python3
"""
Seed Loader Command (Round 15: Flow A - Master Data & Canonical Seed)

Loads the shared canonical seed dataset (products, warehouses, opening stock,
suppliers, and daily sales history) into the Inventory Service PostgreSQL schema.

Usage:
    python -m scripts.load_seed
    python scripts/load_seed.py [--seed-dir PATH] [--no-wipe]
"""

import argparse
import csv
import logging
import re
import sys
from datetime import datetime, UTC, date
from pathlib import Path
from typing import Optional

# Setup path so app can be imported
SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_DIR = SCRIPT_DIR.parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

REPO_ROOT = SERVICE_DIR.parent.parent

from app.database import Base, SessionLocal, engine
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.models.inventory import Inventory
from app.models.inventory_cost_layer import InventoryCostLayer
from app.models.supplier import Supplier
from app.models.sales_history import SalesHistory
from app.services.demand_service import calculate_rolling_average_demand

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_loader")

SKU_RE = re.compile(r"^SKU-\d{6}$")
WH_RE = re.compile(r"^WH-[A-Z]{3}-\d{2}$")
SUP_RE = re.compile(r"^SUP-\d{5}$")


def resolve_seed_directory(custom_path: Optional[str] = None) -> Path:
    """
    Resolves the directory containing the canonical seed CSV files:
    1. custom_path if provided
    2. REPO_ROOT / data-platform / seed / samples (shared seed samples)
    3. REPO_ROOT / data-platform / seed / out (generated full seed)
    4. SERVICE_DIR / data / seed (inventory service seed replica)
    """
    if custom_path:
        p = Path(custom_path).resolve()
        if p.exists() and (p / "skus.csv").exists():
            return p
        logger.warning("Custom seed directory %s does not contain skus.csv; checking fallbacks", p)

    candidates = [
        REPO_ROOT / "data-platform" / "seed" / "samples",
        REPO_ROOT / "data-platform" / "seed" / "out",
        REPO_ROOT / "data-platform" / "seed",
        SERVICE_DIR / "data" / "seed",
    ]

    for c in candidates:
        if c.exists() and (c / "skus.csv").exists():
            logger.info("Found canonical seed directory: %s", c)
            return c

    fallback = SERVICE_DIR / "data" / "seed"
    logger.info("Defaulting to local seed directory: %s", fallback)
    return fallback


def load_suppliers(db, seed_dir: Path, wipe: bool = True) -> int:
    path = seed_dir / "suppliers.csv"
    if not path.exists():
        logger.info("suppliers.csv not present in %s; skipping separate supplier seed", seed_dir)
        return 0

    if wipe:
        db.query(Supplier).delete()
        db.commit()

    count = 0
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = row.get("supplier_id", "").strip()
            if not sid or not SUP_RE.match(sid):
                continue

            sup = db.query(Supplier).filter_by(supplier_id=sid).first()
            name = row.get("name", f"Supplier {sid}")
            lead_time = int(float(row.get("lead_time_days", 7)))

            if not sup:
                db.add(
                    Supplier(
                        supplier_id=sid,
                        supplier_name=name,
                        sku_id="SKU-000001",
                        unit_cost=50.0,
                        lead_time_days=lead_time,
                    )
                )
            else:
                sup.supplier_name = name
                sup.lead_time_days = lead_time
            count += 1

    db.commit()
    logger.info("Loaded %d suppliers into schema", count)
    return count


def load_warehouses(db, seed_dir: Path, wipe: bool = True) -> int:
    path = seed_dir / "warehouses.csv"
    if not path.exists():
        logger.warning("warehouses.csv not found at %s", path)
        return 0

    if wipe:
        db.query(Warehouse).delete()
        db.commit()

    count = 0
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        seen = set()
        for row in reader:
            wh_id = row["warehouse_id"].strip()
            if not WH_RE.match(wh_id):
                raise ValueError(f"Invalid non-canonical warehouse_id in seed: {wh_id}")
            if wh_id in seen:
                continue
            seen.add(wh_id)

            wh = db.query(Warehouse).filter_by(warehouse_id=wh_id).first()
            if not wh:
                wh = Warehouse(
                    warehouse_id=wh_id,
                    name=row.get("name", f"DC {wh_id}"),
                    city=row.get("city", "Unknown"),
                    state=row.get("state", "Unknown"),
                    lat=float(row["lat"]) if row.get("lat") else None,
                    lng=float(row["lng"]) if row.get("lng") else None,
                    capacity_units=int(float(row.get("capacity_units", 100000))),
                    demand_weight=float(row.get("demand_weight", 1.0)),
                    warehouse_type="central" if "BLR" in wh_id else "regional",
                    parent_warehouse_id="WH-BLR-01" if "BLR" not in wh_id else None,
                )
                db.add(wh)
            else:
                wh.name = row.get("name", wh.name)
                wh.city = row.get("city", wh.city)
                wh.state = row.get("state", wh.state)
                wh.capacity_units = int(float(row.get("capacity_units", wh.capacity_units)))
                wh.demand_weight = float(row.get("demand_weight", wh.demand_weight))
            count += 1

    db.commit()
    logger.info("Loaded %d warehouses into schema", count)
    return count


def load_products(db, seed_dir: Path, wipe: bool = True) -> int:
    path = seed_dir / "skus.csv"
    if not path.exists():
        logger.warning("skus.csv not found at %s", path)
        return 0

    if wipe:
        db.query(Product).delete()
        db.commit()

    count = 0
    seen_suppliers = set()
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        seen = set()
        for row in reader:
            sku_id = row["sku_id"].strip()
            if not SKU_RE.match(sku_id):
                raise ValueError(f"Invalid non-canonical sku_id in seed: {sku_id}")
            if sku_id in seen:
                continue
            seen.add(sku_id)

            supplier_id = row.get("supplier_id", "").strip() or None
            if supplier_id and not SUP_RE.match(supplier_id):
                raise ValueError(f"Invalid non-canonical supplier_id in seed: {supplier_id}")

            unit_cost = float(row.get("unit_cost", 50.0))
            prod = db.query(Product).filter_by(sku_id=sku_id).first()
            if not prod:
                prod = Product(
                    sku_id=sku_id,
                    name=row.get("name", f"Product {sku_id}"),
                    category=row.get("category", "General"),
                    pack_size=row.get("pack_size"),
                    unit_price=float(row.get("unit_price", 100.0)),
                    unit_cost=unit_cost,
                    abc_class=row.get("abc_class", "B"),
                    supplier_id=supplier_id,
                )
                db.add(prod)
            else:
                prod.name = row.get("name", prod.name)
                prod.category = row.get("category", prod.category)
                prod.unit_price = float(row.get("unit_price", prod.unit_price))
                prod.unit_cost = unit_cost
                prod.abc_class = row.get("abc_class", prod.abc_class)
                prod.supplier_id = supplier_id

            # Also ensure supplier table has reference for PO drafting (1 supplier per supplier_id)
            if supplier_id and supplier_id not in seen_suppliers:
                seen_suppliers.add(supplier_id)
                sup = db.query(Supplier).filter_by(supplier_id=supplier_id).first()
                if not sup:
                    db.add(
                        Supplier(
                            supplier_id=supplier_id,
                            supplier_name=f"Supplier {supplier_id}",
                            sku_id=sku_id,
                            unit_cost=unit_cost,
                            lead_time_days=4 + (int(sku_id.split("-")[-1]) % 8),
                        )
                    )
            count += 1

    db.commit()
    logger.info("Loaded %d products into schema", count)
    return count


def load_sales_history(db, seed_dir: Path, wipe: bool = True) -> int:
    path = seed_dir / "sales_daily.csv"
    if not path.exists():
        logger.info("sales_daily.csv not found at %s; skipping sales history load", path)
        return 0

    if wipe:
        db.query(SalesHistory).delete()
        db.commit()

    count = 0
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku_id = row.get("sku_id", "").strip()
            wh_id = row.get("warehouse_id", "").strip()
            date_str = row.get("date", "").strip()
            qty = int(float(row.get("quantity_sold", 0)))

            if not SKU_RE.match(sku_id) or not WH_RE.match(wh_id):
                continue
            try:
                sale_dt = datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                continue

            existing = db.query(SalesHistory).filter_by(
                sku_id=sku_id, warehouse_id=wh_id, sale_date=sale_dt
            ).first()
            if not existing:
                db.add(
                    SalesHistory(
                        sku_id=sku_id,
                        warehouse_id=wh_id,
                        sale_date=sale_dt,
                        quantity_sold=qty,
                    )
                )
                count += 1

    db.commit()
    logger.info("Loaded %d sales history records into schema", count)
    return count


def load_opening_stock(db, seed_dir: Path, wipe: bool = True) -> int:
    path = seed_dir / "opening_stock.csv"
    if not path.exists():
        logger.warning("opening_stock.csv not found at %s", path)
        return 0

    if wipe:
        db.query(Inventory).delete()
        db.query(InventoryCostLayer).delete()
        db.commit()

    # Preload products and suppliers for metadata lookup
    products = {p.sku_id: p for p in db.query(Product).all()}
    suppliers = {s.supplier_id: s for s in db.query(Supplier).all()}

    count = 0
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        seen = set()
        for row in reader:
            sku_id = row["sku_id"].strip()
            wh_id = row["warehouse_id"].strip()

            if not SKU_RE.match(sku_id):
                raise ValueError(f"Invalid non-canonical sku_id in opening stock: {sku_id}")
            if not WH_RE.match(wh_id):
                raise ValueError(f"Invalid non-canonical warehouse_id in opening stock: {wh_id}")

            key = (sku_id, wh_id)
            if key in seen:
                continue
            seen.add(key)

            qty = int(float(row.get("quantity_on_hand", 0)))
            prod = products.get(sku_id)
            prod_name = prod.name if prod else f"Product {sku_id}"
            category = prod.category if prod else "General"
            unit_cost = prod.unit_cost if prod else 50.0

            # Determine lead time from supplier metadata
            sup = suppliers.get(prod.supplier_id) if prod and prod.supplier_id else None
            if sup and sup.lead_time_days:
                lead_time = sup.lead_time_days
            elif prod:
                lead_time = 4 + (int(sku_id.split("-")[-1]) % 8)
            else:
                lead_time = 7

            # Calculate actual rolling daily demand from sales_history
            avg_demand = calculate_rolling_average_demand(db, sku_id, wh_id)
            if avg_demand == 0.0:
                avg_demand = round(max(1.0, qty / 10.0), 2)

            safety_stock = max(10, int(avg_demand * 1.5))

            inv = db.query(Inventory).filter_by(sku_id=sku_id, warehouse_id=wh_id).first()
            if not inv:
                inv = Inventory(
                    sku_id=sku_id,
                    warehouse_id=wh_id,
                    product_name=prod_name,
                    category=category,
                    quantity_on_hand=qty,
                    avg_daily_demand=avg_demand,
                    lead_time_days=lead_time,
                    safety_stock=safety_stock,
                    warehouse_type="central" if "BLR" in wh_id else "regional",
                    parent_warehouse_id="WH-BLR-01" if "BLR" not in wh_id else None,
                    version=1,
                )
                db.add(inv)
            else:
                inv.quantity_on_hand = qty
                inv.product_name = prod_name
                inv.category = category
                inv.avg_daily_demand = avg_demand
                inv.lead_time_days = lead_time
                inv.safety_stock = safety_stock

            # Seed cost layer for FIFO valuation
            if qty > 0:
                db.add(
                    InventoryCostLayer(
                        sku_id=sku_id,
                        warehouse_id=wh_id,
                        category=category,
                        quantity_received=qty,
                        quantity_remaining=qty,
                        unit_cost=unit_cost,
                        received_at=datetime.now(UTC),
                    )
                )
            count += 1

    db.commit()
    logger.info("Loaded %d opening stock inventory balances into schema", count)
    return count


def run_loader(seed_dir_path: Optional[str] = None, wipe: bool = True, db = None) -> dict:
    """Executes the full seed loading sequence."""
    Base.metadata.create_all(bind=engine)
    seed_dir = resolve_seed_directory(seed_dir_path)

    session = db or SessionLocal()
    close_session = (db is None)
    try:
        wh_count = load_warehouses(db=session, seed_dir=seed_dir, wipe=wipe)
        sup_count = load_suppliers(db=session, seed_dir=seed_dir, wipe=wipe)
        prod_count = load_products(db=session, seed_dir=seed_dir, wipe=wipe)
        sales_count = load_sales_history(db=session, seed_dir=seed_dir, wipe=wipe)
        stock_count = load_opening_stock(db=session, seed_dir=seed_dir, wipe=wipe)
        return {
            "warehouses_loaded": wh_count,
            "suppliers_loaded": sup_count,
            "products_loaded": prod_count,
            "sales_history_loaded": sales_count,
            "opening_stock_loaded": stock_count,
            "seed_dir": str(seed_dir),
        }
    finally:
        if close_session:
            session.close()


def main():
    parser = argparse.ArgumentParser(description="Load shared canonical seed data into Inventory schema")
    parser.add_argument("--seed-dir", type=str, default=None, help="Path to directory containing seed CSVs")
    parser.add_argument("--no-wipe", action="store_true", help="Do not wipe existing rows before loading")
    args = parser.parse_args()

    logger.info("Starting Inventory canonical seed loader...")
    result = run_loader(seed_dir_path=args.seed_dir, wipe=not args.no_wipe)
    logger.info(
        "Successfully completed seed load: %d warehouses, %d suppliers, %d products, %d sales records, %d opening stock records from %s",
        result["warehouses_loaded"],
        result["suppliers_loaded"],
        result["products_loaded"],
        result["sales_history_loaded"],
        result["opening_stock_loaded"],
        result["seed_dir"],
    )


if __name__ == "__main__":
    main()
