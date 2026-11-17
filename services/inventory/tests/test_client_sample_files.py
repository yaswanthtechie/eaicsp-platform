"""Load the #322 client sample files through the #325 import (issue #325)."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from app.models.product import Product
from app.models.supplier import Supplier
from app.models.warehouse import Warehouse
from app.services.client_import_service import (
    ClientImportValidationError,
    StagingDataset,
    import_staging_dataset,
)

SAMPLES = (
    Path(__file__).resolve().parents[3]
    / "data-platform"
    / "etl"
    / "client_ingest"
    / "samples"
    / "client_format"
)

# Stand-in for the #323 loader's ID mapping, until it is merged. Warehouse
# codes map to the seed's IATA-coded warehouses (Mumbai is BOM, Chennai is MAA).
WAREHOUSE_IDS = {
    "BLR-01": "WH-BLR-01",
    "CHE-01": "WH-MAA-01",
    "DEL-01": "WH-DEL-01",
    "HYD-01": "WH-HYD-01",
    "MUM-01": "WH-BOM-01",
}


def _read(name: str) -> list[dict[str, str]]:
    with (SAMPLES / f"{name}.csv").open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _id_maps() -> tuple[dict[str, str], dict[str, str]]:
    product_codes = sorted({row["product_code"] for row in _read("product_master")})
    supplier_codes = sorted({row["supplier_code"] for row in _read("supplier_master")})
    sku_ids = {code: f"SKU-{i:06d}" for i, code in enumerate(product_codes, start=1)}
    supplier_ids = {
        code: f"SUP-{i:05d}" for i, code in enumerate(supplier_codes, start=1)
    }
    return sku_ids, supplier_ids


def _staged(sku_ids, supplier_ids) -> tuple[list[dict], list[dict]]:
    """Add canonical ID columns the way the #323 loader does.

    Rows the loader would reject for an unknown code are left out.
    """
    snapshots = []
    for row in _read("inventory_snapshot"):
        if row["product_code"] in sku_ids and row["warehouse_code"] in WAREHOUSE_IDS:
            snapshots.append(
                {
                    **row,
                    "sku_id": sku_ids[row["product_code"]],
                    "warehouse_id": WAREHOUSE_IDS[row["warehouse_code"]],
                }
            )
    orders = []
    for row_num, row in enumerate(_read("purchase_order_history"), start=1):
        if (
            row["product_code"] in sku_ids
            and row["warehouse_code"] in WAREHOUSE_IDS
            and row["supplier_code"] in supplier_ids
        ):
            year = row["order_date"][:4] if row["order_date"][:4].isdigit() else "2026"
            orders.append(
                {
                    **row,
                    "po_id": f"PO-{year}-{row_num:06d}",
                    "sku_id": sku_ids[row["product_code"]],
                    "warehouse_id": WAREHOUSE_IDS[row["warehouse_code"]],
                    "supplier_id": supplier_ids[row["supplier_code"]],
                }
            )
    return snapshots, orders


def _is_valid_snapshot(row: dict) -> bool:
    return int(row["quantity_on_hand"]) >= 0


def _is_valid_order(row: dict) -> bool:
    try:
        date.fromisoformat(row["expected_date"])
    except ValueError:
        return False
    return int(row["quantity_ordered"]) > 0


@pytest.fixture
def master_data(db_session):
    sku_ids, supplier_ids = _id_maps()
    for code, sku_id in sku_ids.items():
        db_session.add(
            Product(
                sku_id=sku_id,
                name=code,
                category="Sample",
                unit_of_measure="PCS",
                unit_cost=100.0,
                unit_price=150.0,
                is_active=True,
            )
        )
    for code, warehouse_id in WAREHOUSE_IDS.items():
        db_session.add(
            Warehouse(
                warehouse_id=warehouse_id,
                name=code,
                city="City",
                state="State",
                country="India",
                pincode="560001",
                warehouse_type="regional",
                capacity_units=10000,
            )
        )
    for code, supplier_id in supplier_ids.items():
        db_session.add(
            Supplier(
                supplier_id=supplier_id,
                supplier_name=code,
                lead_time_days=7,
                unit_cost=100.0,
                sku_id="SKU-000001",
            )
        )
    db_session.commit()
    return sku_ids, supplier_ids


def test_sample_files_with_invalid_rows_fail_the_load_cleanly(db_session, master_data):
    snapshots, orders = _staged(*master_data)
    # Row 251 is the sample's negative quantity_on_hand row; it reuses the key
    # of row 1, so the duplicate check reports it first.
    with pytest.raises(
        ClientImportValidationError, match=r"inventory_snapshots\[row 251\]"
    ):
        import_staging_dataset(
            db_session,
            StagingDataset(
                inventory_snapshots=snapshots, purchase_order_history=orders
            ),
            dry_run=True,
        )


def test_sample_files_load_and_ignore_open_and_cancelled_pos(db_session, master_data):
    snapshots, orders = _staged(*master_data)
    snapshots = [row for row in snapshots if _is_valid_snapshot(row)]
    orders = [row for row in orders if _is_valid_order(row)]
    summary = import_staging_dataset(
        db_session,
        StagingDataset(inventory_snapshots=snapshots, purchase_order_history=orders),
        dry_run=False,
    )
    statuses = [row["po_status"] for row in orders]
    assert summary.inventory_snapshots.added == 250
    assert summary.purchase_order_history.added == 365
    assert (
        statuses.count("Received"),
        statuses.count("Open"),
        statuses.count("Cancelled"),
    ) == (338, 12, 15)
    received = sum(p.received_po_count for p in summary.supplier_performance)
    open_count = sum(p.open_po_count for p in summary.supplier_performance)
    cancelled = sum(p.cancelled_po_count for p in summary.supplier_performance)
    assert received == statuses.count("Received")
    assert open_count == statuses.count("Open")
    assert cancelled == statuses.count("Cancelled")
    # Every canonical ID that reached Inventory came from the mapping, never
    # from a reformatted client code.
    assert {r.warehouse_id for r in summary.snapshot_records} <= set(
        WAREHOUSE_IDS.values()
    )
    assert "WH-MUM-01" not in {r.warehouse_id for r in summary.snapshot_records}
