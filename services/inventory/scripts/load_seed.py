#!/usr/bin/env python3
"""
Seed Loader Command (Round 15: Flow A - Master Data & Canonical Seed)

Loads the shared canonical seed (data-platform/seed, owned by Vivek) into the
Inventory schema: warehouses, products, suppliers, daily sales history and
current stock.

Run migrations first, then generate the seed and load it:
  alembic upgrade head
  (cd ../../data-platform && python -m seed.generate --out out/)
  python scripts/load_seed.py [--seed-dir PATH] [--wipe]

The whole load is one transaction: it either fully succeeds or changes
nothing. Re-running it upserts, so it never duplicates rows.
--wipe clears the seeded tables first (use it to reset stock valuation).
"""

import argparse
import csv
import logging
import re
import sys
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import insert

# Setup path so app can be imported
SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_DIR = SCRIPT_DIR.parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))
REPO_ROOT = SERVICE_DIR.parent.parent

from app.database import SessionLocal
from app.models.inventory import Inventory
from app.models.inventory_cost_layer import InventoryCostLayer
from app.models.product import Product
from app.models.sales_history import SalesHistory
from app.models.supplier import Supplier
from app.models.warehouse import Warehouse
from app.services.demand_service import calculate_rolling_average_demand

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_loader")

SKU_RE = re.compile(r"^SKU-\d{6}$")
WH_RE = re.compile(r"^WH-[A-Z]{3}-\d{2}$")
SUP_RE = re.compile(r"^SUP-\d{5}$")

# Output of `python -m seed.generate --out out/`, run from data-platform/.
DEFAULT_SEED_DIR = REPO_ROOT / "data-platform" / "out"

REQUIRED_FILES = (
    "warehouses.csv",
    "skus.csv",
    "suppliers.csv",
    "sales_daily.csv",
    "current_stock.csv",
)

# The seed has no warehouse hierarchy. Bengaluru is the national DC and every
# other warehouse replenishes from it.
HUB_WAREHOUSE_ID = "WH-BLR-01"
DEFAULT_LEAD_TIME_DAYS = 7
SAFETY_STOCK_DAYS = 1.5  # safety stock = this many days of average demand
MIN_SAFETY_STOCK = 10
SALES_BATCH_SIZE = 5000


def resolve_seed_directory(custom_path: Optional[str] = None) -> Path:
    """Return the seed directory, or fail loudly if any seed file is missing."""
    seed_dir = Path(custom_path).resolve() if custom_path else DEFAULT_SEED_DIR
    missing = [name for name in REQUIRED_FILES if not (seed_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Seed directory {seed_dir} is missing {', '.join(missing)}. "
            "Generate it with: cd data-platform && python -m seed.generate --out out/"
        )
    return seed_dir


def _read_csv(seed_dir: Path, name: str) -> Iterator[dict]:
    with open(seed_dir / name, "r", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def _require(pattern: re.Pattern, value: Optional[str], field: str) -> str:
    value = (value or "").strip()
    if not pattern.match(value):
        raise ValueError(f"Invalid non-canonical {field} in seed: {value!r}")
    return value


def _upsert(db, model, existing: dict, key, key_fields: dict, values: dict):
    """Update the row in `existing` or add a new one. `existing` also catches duplicates within the same file, since the session does not autoflush."""
    obj = existing.get(key)
    if obj is None:
        obj = model(**key_fields, **values)
        db.add(obj)
        existing[key] = obj
    else:
        for field, value in values.items():
            setattr(obj, field, value)
    return obj


def load_warehouses(db, seed_dir: Path) -> int:
    existing = {w.warehouse_id: w for w in db.query(Warehouse)}
    count = 0
    for row in _read_csv(seed_dir, "warehouses.csv"):
        wh_id = _require(WH_RE, row.get("warehouse_id"), "warehouse_id")
        is_hub = wh_id == HUB_WAREHOUSE_ID
        _upsert(
            db,
            Warehouse,
            existing,
            wh_id,
            {"warehouse_id": wh_id},
            {
                "name": row["name"],
                "city": row["city"],
                "state": row["state"],
                "lat": float(row["lat"]) if row.get("lat") else None,
                "lng": float(row["lng"]) if row.get("lng") else None,
                "capacity_units": int(float(row["capacity_units"])),
                "demand_weight": float(row.get("demand_weight") or 1.0),
                "warehouse_type": "central" if is_hub else "regional",
                "parent_warehouse_id": None if is_hub else HUB_WAREHOUSE_ID,
            },
        )
        count += 1
    db.flush()
    logger.info("Loaded %d warehouses", count)
    return count


def load_products(db, seed_dir: Path) -> int:
    existing = {p.sku_id: p for p in db.query(Product)}
    count = 0
    for row in _read_csv(seed_dir, "skus.csv"):
        sku_id = _require(SKU_RE, row.get("sku_id"), "sku_id")
        supplier_id = _require(SUP_RE, row.get("supplier_id"), "supplier_id")
        _upsert(
            db,
            Product,
            existing,
            sku_id,
            {"sku_id": sku_id},
            {
                "name": row["name"],
                "category": row["category"],
                "pack_size": row.get("pack_size") or None,
                "unit_price": float(row["unit_price"]),
                "unit_cost": float(row["unit_cost"]),
                "abc_class": row.get("abc_class") or None,
                "supplier_id": supplier_id,
            },
        )
        count += 1
    db.flush()
    logger.info("Loaded %d products", count)
    return count


def load_suppliers(db, seed_dir: Path) -> int:
    """
    Inventory's read copy of Supplier Portal's master data, for PO drafting.
    The suppliers table holds one sku_id per supplier, so it gets the supplier's
    first product. select_supplier() resolves every other SKU through
    Product.supplier_id. Must run after load_products.
    """
    first_product = {}
    for product in db.query(Product).order_by(Product.sku_id):
        first_product.setdefault(product.supplier_id, product)

    existing = {s.supplier_id: s for s in db.query(Supplier)}
    count = 0
    for row in _read_csv(seed_dir, "suppliers.csv"):
        supplier_id = _require(SUP_RE, row.get("supplier_id"), "supplier_id")
        product = first_product.get(supplier_id)
        _upsert(
            db,
            Supplier,
            existing,
            supplier_id,
            {"supplier_id": supplier_id},
            {
                "supplier_name": row["name"],
                # A supplier with no SKU in the catalog is kept for compliance
                # screening but never matches a SKU lookup.
                "sku_id": product.sku_id if product else "",
                "unit_cost": product.unit_cost if product else 0.0,
                "lead_time_days": int(float(row["lead_time_days"])),
            },
        )
        count += 1
    db.flush()
    logger.info("Loaded %d suppliers", count)
    return count


def load_sales_history(db, seed_dir: Path) -> int:
    existing = set(
        db.query(SalesHistory.sku_id, SalesHistory.warehouse_id, SalesHistory.sale_date)
    )
    batch = []
    count = 0
    for row in _read_csv(seed_dir, "sales_daily.csv"):
        sku_id = _require(SKU_RE, row.get("sku_id"), "sku_id")
        wh_id = _require(WH_RE, row.get("warehouse_id"), "warehouse_id")
        key = (sku_id, wh_id, date.fromisoformat(row["date"]))
        if key in existing:
            continue
        existing.add(key)
        batch.append(
            {
                "sku_id": sku_id,
                "warehouse_id": wh_id,
                "sale_date": key[2],
                "quantity_sold": int(float(row["quantity_sold"])),
            }
        )
        if len(batch) >= SALES_BATCH_SIZE:
            db.execute(insert(SalesHistory), batch)
            count += len(batch)
            batch = []
    if batch:
        db.execute(insert(SalesHistory), batch)
        count += len(batch)
    logger.info("Loaded %d new sales history rows", count)
    return count


def load_current_stock(db, seed_dir: Path) -> int:
    """
    Stock on hand from current_stock.csv (the snapshot at the end of the sales
    history). Must run after the other loaders.
    """
    products = {p.sku_id: p for p in db.query(Product)}
    suppliers = {s.supplier_id: s for s in db.query(Supplier)}
    warehouses = {w.warehouse_id: w for w in db.query(Warehouse)}
    existing = {(i.sku_id, i.warehouse_id): i for i in db.query(Inventory)}
    has_cost_layer = set(
        db.query(InventoryCostLayer.sku_id, InventoryCostLayer.warehouse_id).distinct()
    )
    count = 0
    for row in _read_csv(seed_dir, "current_stock.csv"):
        sku_id = _require(SKU_RE, row.get("sku_id"), "sku_id")
        wh_id = _require(WH_RE, row.get("warehouse_id"), "warehouse_id")
        product = products.get(sku_id)
        warehouse = warehouses.get(wh_id)
        if product is None or warehouse is None:
            raise ValueError(
                f"current_stock.csv references unknown SKU/warehouse: {sku_id} / {wh_id}"
            )
        snapshot_date = date.fromisoformat(row["snapshot_date"])
        qty = int(float(row["quantity_on_hand"]))
        supplier = suppliers.get(product.supplier_id)
        lead_time = supplier.lead_time_days if supplier else DEFAULT_LEAD_TIME_DAYS
        avg_demand = calculate_rolling_average_demand(
            db, sku_id, wh_id, end_date=snapshot_date
        )
        key = (sku_id, wh_id)
        inv = _upsert(
            db,
            Inventory,
            existing,
            key,
            {"sku_id": sku_id, "warehouse_id": wh_id},
            {
                "product_name": product.name,
                "category": product.category,
                "quantity_on_hand": qty,
                "avg_daily_demand": avg_demand,
                "lead_time_days": lead_time,
                "safety_stock": max(MIN_SAFETY_STOCK, int(avg_demand * SAFETY_STOCK_DAYS)),
                "warehouse_type": warehouse.warehouse_type,
                "parent_warehouse_id": warehouse.parent_warehouse_id,
            },
        )
        inv.version = (inv.version or 0) + 1

        # One opening FIFO layer per SKU/warehouse. A re-run never adds another.
        if qty > 0 and key not in has_cost_layer:
            db.add(
                InventoryCostLayer(
                    sku_id=sku_id,
                    warehouse_id=wh_id,
                    category=product.category,
                    quantity_received=qty,
                    quantity_remaining=qty,
                    unit_cost=product.unit_cost,
                    received_at=datetime.combine(snapshot_date, time.min, tzinfo=UTC),
                )
            )
            has_cost_layer.add(key)
        count += 1
    db.flush()
    logger.info("Loaded %d current stock rows", count)
    return count


def _wipe(db) -> None:
    for model in (
        InventoryCostLayer,
        Inventory,
        SalesHistory,
        Supplier,
        Product,
        Warehouse,
    ):
        db.query(model).delete()
    db.flush()


def run_loader(
    seed_dir_path: Optional[str] = None, wipe: bool = False, db=None
) -> dict:
    """Load the whole seed in one transaction. Rolls back everything on any error."""
    seed_dir = resolve_seed_directory(seed_dir_path)
    session = db or SessionLocal()
    try:
        if wipe:
            _wipe(session)
        result = {
            "warehouses_loaded": load_warehouses(session, seed_dir),
            "products_loaded": load_products(session, seed_dir),
            "suppliers_loaded": load_suppliers(session, seed_dir),
            "sales_history_loaded": load_sales_history(session, seed_dir),
            "current_stock_loaded": load_current_stock(session, seed_dir),
            "seed_dir": str(seed_dir),
        }
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
    finally:
        if db is None:
            session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Load shared canonical seed data into Inventory schema"
    )
    parser.add_argument(
        "--seed-dir",
        type=str,
        default=None,
        help=f"Seed CSV directory (default: {DEFAULT_SEED_DIR})",
    )
    parser.add_argument(
        "--wipe", action="store_true", help="Delete seeded tables before loading"
    )
    args = parser.parse_args()

    result = run_loader(seed_dir_path=args.seed_dir, wipe=args.wipe)
    logger.info("Seed load complete: %s", result)


if __name__ == "__main__":
    main()
