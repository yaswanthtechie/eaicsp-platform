"""Focused deterministic tests for R15-B8 Client Data Readiness (#324)."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest
import yaml
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app import cli
from app.models.product import Product
from app.models.supplier import Supplier, SupplierLeadTime
from app.models.warehouse import Warehouse
from app.services.client_import_service import (
    STAGING_TABLES,
    ClientImportError,
    ClientImportValidationError,
    StagingDataset,
    import_staging_dataset,
    run_client_data_import,
)


def _write_csv(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def _valid_product(
    sku_id: str = "SKU-000001",
    *,
    product_code: str = "PRD-10482",
    name: str = "Synthetic Widget A",
    category: str = "Hardware",
    unit_of_measure: str = "PCS",
    unit_cost: str = "42.50",
    unit_price: str = "55.00",
    is_active: str = "true",
) -> dict[str, str]:
    return {
        "product_code": product_code,
        "product_name": name,
        "category": category,
        "unit_of_measure": unit_of_measure,
        "unit_cost": unit_cost,
        "unit_price": unit_price,
        "is_active": is_active,
        "sku_id": sku_id,
    }


def _valid_warehouse(
    warehouse_id: str = "WH-BLR-01",
    *,
    warehouse_code: str = "BLR-01",
    name: str = "Bengaluru Distribution Centre",
    city: str = "Bengaluru",
    state: str = "Karnataka",
    country: str = "India",
    pincode: str = "560001",
    warehouse_type: str = "Regional",
) -> dict[str, str]:
    return {
        "warehouse_code": warehouse_code,
        "warehouse_name": name,
        "city": city,
        "state": state,
        "country": country,
        "pincode": pincode,
        "warehouse_type": warehouse_type,
        "warehouse_id": warehouse_id,
    }


def _valid_lead_time(
    supplier_id: str = "SUP-00001",
    sku_id: str = "SKU-000001",
    *,
    average_lead_time_days: int = 10,
    minimum_lead_time_days: int = 5,
    maximum_lead_time_days: int = 15,
    effective_date: str = "2026-01-01",
) -> dict[str, object]:
    return {
        "supplier_code": "SUP-2231",  # noncanonical-ok
        "product_code": "PRD-10482",
        "average_lead_time_days": average_lead_time_days,
        "minimum_lead_time_days": minimum_lead_time_days,
        "maximum_lead_time_days": maximum_lead_time_days,
        "effective_date": effective_date,
        "supplier_id": supplier_id,
        "sku_id": sku_id,
    }


def _seed_supplier(
    db_session, supplier_id: str = "SUP-00001", name: str = "Synthetic Supplier"
) -> None:
    db_session.add(
        Supplier(
            supplier_id=supplier_id,
            supplier_name=name,
            sku_id="SKU-000001",
            unit_cost=10.0,
            lead_time_days=7,
        )
    )
    db_session.commit()


def test_alignment_with_322_spec_and_synthetic_samples(tmp_path: Path, db_session):
    repo_root = Path(__file__).resolve().parents[3]
    client_ingest = repo_root / "data-platform" / "etl" / "client_ingest"
    spec = yaml.safe_load((client_ingest / "spec.yaml").read_text(encoding="utf-8"))

    assert STAGING_TABLES["products"] == spec["files"]["product_master"]["staging_table"]
    assert STAGING_TABLES["warehouses"] == spec["files"]["warehouse_master"]["staging_table"]
    assert (
        STAGING_TABLES["supplier_lead_times"]
        == spec["files"]["supplier_lead_times"]["staging_table"]
    )

    samples = client_ingest / "samples" / "client_format"
    with (samples / "product_master.csv").open(encoding="utf-8", newline="") as f:
        raw_products = list(csv.DictReader(f))[:50]
    with (samples / "warehouse_master.csv").open(encoding="utf-8", newline="") as f:
        raw_warehouses = list(csv.DictReader(f))[:5]
    with (samples / "supplier_master.csv").open(encoding="utf-8", newline="") as f:
        raw_suppliers = list(csv.DictReader(f))[:20]
    with (samples / "supplier_lead_times.csv").open(encoding="utf-8", newline="") as f:
        raw_lead_times = list(csv.DictReader(f))[:100]

    prod_map = {r["product_code"]: f"SKU-{i + 1:06d}" for i, r in enumerate(raw_products)}
    sup_map = {r["supplier_code"]: f"SUP-{i + 1:05d}" for i, r in enumerate(raw_suppliers)}
    iata_map = spec["warehouse_city_to_iata"]
    wh_map = {
        r["warehouse_code"]: f"WH-{iata_map[r['city']]}-01"
        for r in raw_warehouses
    }

    # Suppliers are owned by Supplier Portal and pre-exist in Inventory's read copy.
    for r in raw_suppliers:
        db_session.add(
            Supplier(
                supplier_id=sup_map[r["supplier_code"]],
                supplier_name=r["supplier_name"],
                sku_id="SKU-000001",
                unit_cost=10.0,
                lead_time_days=7,
            )
        )
    db_session.commit()

    _write_csv(
        tmp_path / "stg_product_master.csv",
        [
            "product_code",
            "product_name",
            "category",
            "unit_of_measure",
            "unit_price",
            "unit_cost",
            "is_active",
            "sku_id",
        ],
        [
            [
                r["product_code"],
                r["product_name"],
                r["category"],
                r["unit_of_measure"],
                r["unit_price"],
                round(float(r["unit_price"]) * 0.8, 2),
                r["is_active"],
                prod_map[r["product_code"]],
            ]
            for r in raw_products
        ],
    )
    _write_csv(
        tmp_path / "stg_warehouse_master.csv",
        ["warehouse_code", "warehouse_name", "city", "state", "country", "pincode", "warehouse_type", "warehouse_id"],
        [
            [
                r["warehouse_code"],
                r["warehouse_name"],
                r["city"],
                r["state"],
                r["country"],
                r["pincode"],
                r["warehouse_type"],
                wh_map[r["warehouse_code"]],
            ]
            for r in raw_warehouses
        ],
    )
    _write_csv(
        tmp_path / "stg_supplier_lead_times.csv",
        [
            "supplier_code",
            "product_code",
            "average_lead_time_days",
            "minimum_lead_time_days",
            "maximum_lead_time_days",
            "effective_date",
            "supplier_id",
            "sku_id",
        ],
        [
            [
                r["supplier_code"],
                r["product_code"],
                r["average_lead_time_days"],
                r["minimum_lead_time_days"],
                r["maximum_lead_time_days"],
                r["effective_date"],
                sup_map[r["supplier_code"]],
                prod_map[r["product_code"]],
            ]
            for r in raw_lead_times
        ],
    )

    dry = run_client_data_import(db=db_session, staging_dir=tmp_path, dry_run=True)
    assert dry.products.added == 50
    assert dry.warehouses.added == 5
    assert dry.supplier_lead_times.added == 100
    assert db_session.query(Product).count() == 0
    assert db_session.query(Warehouse).count() == 0
    assert db_session.query(SupplierLeadTime).count() == 0

    first = run_client_data_import(db=db_session, staging_dir=tmp_path, dry_run=False)
    assert first.products.added == 50
    assert first.warehouses.added == 5
    assert first.supplier_lead_times.added == 100
    assert db_session.query(Product).count() == 50
    assert db_session.query(Warehouse).count() == 5
    assert db_session.query(SupplierLeadTime).count() == 100
    assert all(w.warehouse_type == "regional" for w in db_session.query(Warehouse).all())

    second = run_client_data_import(db=db_session, staging_dir=tmp_path, dry_run=False)
    assert (second.products.added, second.products.updated, second.products.unchanged) == (0, 0, 50)
    assert (second.warehouses.added, second.warehouses.updated, second.warehouses.unchanged) == (0, 0, 5)
    assert (
        second.supplier_lead_times.added,
        second.supplier_lead_times.updated,
        second.supplier_lead_times.unchanged,
    ) == (0, 0, 100)


def test_product_upsert_canonical_identity_and_idempotency(db_session):
    p1 = _valid_product("SKU-000001", product_code="PRD-10482", name="Bolt", unit_cost="12.5")
    res1 = import_staging_dataset(db_session, StagingDataset(products=[p1]))
    assert (res1.products.added, res1.products.updated, res1.products.unchanged) == (1, 0, 0)

    stored = db_session.get(Product, "SKU-000001")
    assert stored is not None
    assert stored.name == "Bolt"
    assert stored.unit_of_measure == "PCS"
    assert stored.unit_cost == 12.5
    assert db_session.get(Product, "PRD-10482") is None

    # Unchanged re-import does nothing.
    res2 = import_staging_dataset(db_session, StagingDataset(products=[p1]))
    assert (res2.products.added, res2.products.updated, res2.products.unchanged) == (0, 0, 1)

    # Same client product_code with updated fields updates in place without duplicate rows.
    p1_updated = _valid_product(
        "SKU-000001",
        product_code="PRD-10482",
        name="Bolt M8",
        category="Fasteners",
        unit_of_measure="BOX",
        unit_cost="19.75",
    )
    res3 = import_staging_dataset(db_session, StagingDataset(products=[p1_updated]))
    assert (res3.products.added, res3.products.updated, res3.products.unchanged) == (0, 1, 0)
    assert db_session.query(Product).count() == 1
    db_session.refresh(stored)
    assert stored.name == "Bolt M8"
    assert stored.category == "Fasteners"
    assert stored.unit_of_measure == "BOX"
    assert stored.unit_cost == 19.75


def test_new_product_without_unit_cost_fails_and_existing_preserves_cost(db_session):
    no_cost_new = _valid_product("SKU-000050", unit_price="120.00")
    no_cost_new.pop("unit_cost")

    with pytest.raises(ClientImportValidationError, match="has no unit_cost in staging"):
        import_staging_dataset(
            db_session,
            StagingDataset(
                products=[no_cost_new],
                warehouses=[_valid_warehouse("WH-BLR-01")],
            ),
        )
    assert db_session.query(Product).count() == 0
    assert db_session.query(Warehouse).count() == 0

    # Existing product keeps its unit_cost when staging updates unit_price without unit_cost.
    seeded = _valid_product("SKU-000050", unit_price="100.00", unit_cost="60.00")
    import_staging_dataset(db_session, StagingDataset(products=[seeded]))

    update_price_only = _valid_product("SKU-000050", name="Updated Prod", unit_price="135.00")
    update_price_only.pop("unit_cost")
    res = import_staging_dataset(db_session, StagingDataset(products=[update_price_only]))
    assert (res.products.added, res.products.updated, res.products.unchanged) == (0, 1, 0)
    prod = db_session.get(Product, "SKU-000050")
    assert prod is not None
    assert prod.unit_price == 135.0
    assert prod.unit_cost == 60.0


def test_warehouse_upsert_canonical_identity_and_idempotency(db_session):
    w1 = _valid_warehouse("WH-BLR-01", warehouse_code="BLR-01", name="BLR Hub")
    res1 = import_staging_dataset(db_session, StagingDataset(warehouses=[w1]))
    assert (res1.warehouses.added, res1.warehouses.updated, res1.warehouses.unchanged) == (1, 0, 0)

    wh = db_session.get(Warehouse, "WH-BLR-01")
    assert wh is not None
    assert wh.country == "India"
    assert wh.warehouse_type == "regional"
    assert db_session.get(Warehouse, "BLR-01") is None

    res2 = import_staging_dataset(db_session, StagingDataset(warehouses=[w1]))
    assert (res2.warehouses.added, res2.warehouses.updated, res2.warehouses.unchanged) == (0, 0, 1)

    w1_updated = _valid_warehouse(
        "WH-BLR-01",
        warehouse_code="BLR-01",
        name="BLR Central Hub",
        city="Bengaluru",
        state="Karnataka",
        country="IN",
        warehouse_type="Central",
    )
    res3 = import_staging_dataset(db_session, StagingDataset(warehouses=[w1_updated]))
    assert (res3.warehouses.added, res3.warehouses.updated, res3.warehouses.unchanged) == (0, 1, 0)
    assert db_session.query(Warehouse).count() == 1
    db_session.refresh(wh)
    assert wh.name == "BLR Central Hub"
    assert wh.country == "IN"
    assert wh.warehouse_type == "central"


def test_supplier_lead_times_upsert_idempotency_and_existing_supplier_fk(db_session):
    _seed_supplier(db_session, "SUP-00001")
    dataset = StagingDataset(
        products=[
            _valid_product("SKU-000001", product_code="PRD-10001"),
            _valid_product("SKU-000002", product_code="PRD-10002", name="Synthetic Widget B"),
        ],
        supplier_lead_times=[
            _valid_lead_time("SUP-00001", "SKU-000001", average_lead_time_days=8),
            _valid_lead_time("SUP-00001", "SKU-000002", average_lead_time_days=12, effective_date="2026-02-01"),
        ],
    )
    res1 = import_staging_dataset(db_session, dataset)
    assert (res1.supplier_lead_times.added, res1.supplier_lead_times.updated) == (2, 0)
    assert db_session.query(Supplier).count() == 1
    assert db_session.query(SupplierLeadTime).count() == 2

    res2 = import_staging_dataset(db_session, dataset)
    assert (
        res2.supplier_lead_times.added,
        res2.supplier_lead_times.updated,
        res2.supplier_lead_times.unchanged,
    ) == (0, 0, 2)

    dataset.supplier_lead_times[0] = _valid_lead_time(
        "SUP-00001",
        "SKU-000001",
        average_lead_time_days=9,
        minimum_lead_time_days=6,
        maximum_lead_time_days=14,
    )
    res3 = import_staging_dataset(db_session, dataset)
    assert (
        res3.supplier_lead_times.added,
        res3.supplier_lead_times.updated,
        res3.supplier_lead_times.unchanged,
    ) == (0, 1, 1)
    updated_lt = db_session.get(SupplierLeadTime, ("SUP-00001", "SKU-000001"))
    assert updated_lt is not None
    assert updated_lt.average_lead_time_days == 9
    assert updated_lt.minimum_lead_time_days == 6
    assert updated_lt.effective_date == date(2026, 1, 1)


def test_unknown_supplier_in_lead_times_or_products_fails_with_zero_writes(db_session):
    dataset = StagingDataset(
        products=[_valid_product("SKU-000001")],
        warehouses=[_valid_warehouse("WH-BLR-01")],
        supplier_lead_times=[_valid_lead_time("SUP-99999", "SKU-000001")],
    )
    with pytest.raises(ClientImportValidationError, match="unknown supplier_id"):
        import_staging_dataset(db_session, dataset)

    assert db_session.query(Supplier).count() == 0
    assert db_session.query(Product).count() == 0
    assert db_session.query(Warehouse).count() == 0
    assert db_session.query(SupplierLeadTime).count() == 0

    prod_with_missing_sup = {**_valid_product("SKU-000001"), "supplier_id": "SUP-99999"}
    with pytest.raises(ClientImportValidationError, match="not in suppliers"):
        import_staging_dataset(db_session, StagingDataset(products=[prod_with_missing_sup]))
    assert db_session.query(Product).count() == 0


def test_oversized_product_name_and_invalid_warehouse_type_fail_cleanly(db_session):
    oversized = _valid_product("SKU-000001", name="P" * 300)
    with pytest.raises(ClientImportValidationError, match="longer than 255 characters"):
        import_staging_dataset(
            db_session,
            StagingDataset(
                products=[oversized],
                warehouses=[_valid_warehouse("WH-BLR-01")],
            ),
        )
    assert db_session.query(Product).count() == 0
    assert db_session.query(Warehouse).count() == 0

    bad_wh_type = _valid_warehouse("WH-BLR-01", warehouse_type="mega_hub")
    with pytest.raises(ClientImportValidationError, match="invalid warehouse_type"):
        import_staging_dataset(db_session, StagingDataset(warehouses=[bad_wh_type]))
    assert db_session.query(Warehouse).count() == 0


def test_dry_run_performs_zero_db_writes_and_computes_accurate_counts(db_session):
    _seed_supplier(db_session, "SUP-00001")
    initial = StagingDataset(
        products=[
            _valid_product("SKU-000001", product_code="PRD-10001", name="Unchanged"),
            _valid_product("SKU-000002", product_code="PRD-10002", name="Old Name", unit_cost="20.0"),
        ],
        warehouses=[
            _valid_warehouse("WH-BLR-01", warehouse_code="BLR-01", name="BLR Existing"),
            _valid_warehouse("WH-BOM-01", warehouse_code="MUM-01", name="BOM Old", city="Mumbai", state="Maharashtra"),
        ],
        supplier_lead_times=[
            _valid_lead_time("SUP-00001", "SKU-000001", average_lead_time_days=10),
            _valid_lead_time("SUP-00001", "SKU-000002", average_lead_time_days=12),
        ],
    )
    import_staging_dataset(db_session, initial)

    next_batch = StagingDataset(
        products=[
            _valid_product("SKU-000001", product_code="PRD-10001", name="Unchanged"),
            _valid_product("SKU-000002", product_code="PRD-10002", name="New Name", unit_cost="25.0"),
            _valid_product("SKU-000003", product_code="PRD-10003", name="Added Prod"),
        ],
        warehouses=[
            _valid_warehouse("WH-BLR-01", warehouse_code="BLR-01", name="BLR Existing"),
            _valid_warehouse("WH-BOM-01", warehouse_code="MUM-01", name="BOM Updated", city="Mumbai", state="Maharashtra"),
            _valid_warehouse("WH-DEL-01", warehouse_code="DEL-01", name="DEL New", city="New Delhi", state="Delhi"),
        ],
        supplier_lead_times=[
            _valid_lead_time("SUP-00001", "SKU-000001", average_lead_time_days=10),
            _valid_lead_time("SUP-00001", "SKU-000002", average_lead_time_days=14),
            _valid_lead_time("SUP-00001", "SKU-000003", average_lead_time_days=7),
        ],
    )
    dry = import_staging_dataset(db_session, next_batch, dry_run=True)
    assert (dry.products.added, dry.products.updated, dry.products.unchanged) == (1, 1, 1)
    assert (dry.warehouses.added, dry.warehouses.updated, dry.warehouses.unchanged) == (1, 1, 1)
    assert (
        dry.supplier_lead_times.added,
        dry.supplier_lead_times.updated,
        dry.supplier_lead_times.unchanged,
    ) == (1, 1, 1)

    assert db_session.query(Product).count() == 2
    assert db_session.query(Warehouse).count() == 2
    assert db_session.query(SupplierLeadTime).count() == 2
    assert db_session.get(Product, "SKU-000002").name == "Old Name"
    assert db_session.get(Warehouse, "WH-BOM-01").name == "BOM Old"
    assert db_session.get(SupplierLeadTime, ("SUP-00001", "SKU-000002")).average_lead_time_days == 12


@pytest.mark.parametrize(
    ("mutator", "expected_msg"),
    [
        (
            lambda ds: ds.products.append(_valid_product("")),
            "sku_id",
        ),
        (
            lambda ds: ds.products.append(_valid_product("PRD-99999")),
            "non-canonical sku_id",
        ),
        (
            lambda ds: ds.products.append(
                _valid_product("SKU-000002", product_code="PRD-10002", unit_cost="-10")
            ),
            "unit_cost",
        ),
        (
            lambda ds: ds.products.append(_valid_product("SKU-000001", product_code="PRD-OTHER")),
            "duplicate canonical sku_id",
        ),
        (
            lambda ds: ds.warehouses.append(_valid_warehouse("")),
            "warehouse_id",
        ),
        (
            lambda ds: ds.warehouses.append(_valid_warehouse("WH001")),  # noncanonical-ok
            "non-canonical warehouse_id",
        ),
        (
            lambda ds: ds.warehouses.append(_valid_warehouse("WH-BLR-01", warehouse_code="BLR-ALT")),
            "duplicate canonical warehouse_id",
        ),
        (
            lambda ds: ds.supplier_lead_times.append(_valid_lead_time("", "SKU-000001")),
            "supplier_id",
        ),
        (
            lambda ds: ds.supplier_lead_times.__setitem__(
                0, _valid_lead_time("SUP-00001", "SKU-000001", average_lead_time_days=0)
            ),
            "average_lead_time_days",
        ),
        (
            lambda ds: ds.supplier_lead_times.__setitem__(
                0,
                _valid_lead_time(
                    "SUP-00001",
                    "SKU-000001",
                    average_lead_time_days=5,
                    minimum_lead_time_days=8,
                ),
            ),
            "minimum <= average <= maximum",
        ),
        (
            lambda ds: ds.supplier_lead_times.append(_valid_lead_time("SUP-99999", "SKU-000001")),
            "unknown supplier_id",
        ),
        (
            lambda ds: ds.supplier_lead_times.append(_valid_lead_time("SUP-00001", "SKU-999999")),
            "unknown sku_id",
        ),
        (
            lambda ds: ds.supplier_lead_times.append(_valid_lead_time("SUP-00001", "SKU-000001")),
            "duplicate canonical key",
        ),
        (
            lambda ds: ds.products.append(
                {**_valid_product("SKU-000002", product_code="PRD-10002"), None: ["extra-col"]}
            ),
            "malformed staging record",
        ),
    ],
)
def test_validation_failure_raises_clearly_and_rolls_back_transaction(
    db_session, mutator, expected_msg
):
    _seed_supplier(db_session, "SUP-00001")
    baseline = StagingDataset(
        products=[_valid_product("SKU-000001", name="Original")],
        warehouses=[_valid_warehouse("WH-BLR-01", name="Original WH")],
        supplier_lead_times=[_valid_lead_time("SUP-00001", "SKU-000001", average_lead_time_days=10)],
    )
    import_staging_dataset(db_session, baseline)

    failing = StagingDataset(
        products=[_valid_product("SKU-000001", name="Should Rollback")],
        warehouses=[_valid_warehouse("WH-BLR-01", name="Should Rollback WH")],
        supplier_lead_times=[
            _valid_lead_time("SUP-00001", "SKU-000001", average_lead_time_days=11)
        ],
    )
    mutator(failing)

    with pytest.raises(ClientImportValidationError, match=expected_msg):
        import_staging_dataset(db_session, failing)

    assert db_session.query(Product).count() == 1
    assert db_session.get(Product, "SKU-000001").name == "Original"
    assert db_session.query(Warehouse).count() == 1
    assert db_session.get(Warehouse, "WH-BLR-01").name == "Original WH"
    assert db_session.get(SupplierLeadTime, ("SUP-00001", "SKU-000001")).average_lead_time_days == 10


def test_import_from_db_staging_tables(db_session):
    _seed_supplier(db_session, "SUP-00010", name="Staged Supplier")
    staging_names = (
        "stg_product_master",
        "stg_warehouse_master",
        "stg_supplier_lead_times",
    )
    for table_name in staging_names:
        db_session.execute(text(f"DROP TABLE IF EXISTS {table_name}"))

    try:
        db_session.execute(
            text(
                "CREATE TABLE stg_product_master ("
                "product_code TEXT, product_name TEXT, category TEXT, "
                "unit_of_measure TEXT, unit_price DOUBLE PRECISION, "
                "unit_cost DOUBLE PRECISION, is_active BOOLEAN, sku_id TEXT)"
            )
        )
        db_session.execute(
            text(
                "CREATE TABLE stg_warehouse_master ("
                "warehouse_code TEXT, warehouse_name TEXT, city TEXT, state TEXT, "
                "country TEXT, pincode TEXT, warehouse_type TEXT, warehouse_id TEXT)"
            )
        )
        db_session.execute(
            text(
                "CREATE TABLE stg_supplier_lead_times ("
                "supplier_code TEXT, product_code TEXT, average_lead_time_days INTEGER, "
                "minimum_lead_time_days INTEGER, maximum_lead_time_days INTEGER, "
                "effective_date TEXT, supplier_id TEXT, sku_id TEXT)"
            )
        )
        db_session.execute(
            text(
                "INSERT INTO stg_product_master VALUES "
                "('PRD-10482', 'Staged Product', 'Grocery', 'PCS', 99.5, 72.0, TRUE, 'SKU-000010')"
            )
        )
        db_session.execute(
            text(
                "INSERT INTO stg_warehouse_master VALUES "
                "('HYD-01', 'Hyderabad Hub', 'Hyderabad', 'Telangana', 'India', '500001', 'Regional', 'WH-HYD-01')"
            )
        )
        db_session.execute(
            text(
                "INSERT INTO stg_supplier_lead_times VALUES "
                "('SUP-2231', 'PRD-10482', 6, 4, 9, '2026-03-01', 'SUP-00010', 'SKU-000010')"  # noncanonical-ok
            )
        )
        db_session.commit()

        first = run_client_data_import(db=db_session, source="auto")
        assert first.products.added == 1
        assert first.warehouses.added == 1
        assert first.supplier_lead_times.added == 1

        second = run_client_data_import(db=db_session, source="db")
        assert second.products.unchanged == 1
        assert second.warehouses.unchanged == 1
        assert second.supplier_lead_times.unchanged == 1
    finally:
        db_session.rollback()
        for table_name in staging_names:
            db_session.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
        db_session.commit()


def test_cli_import_client_data_dry_run_and_live(tmp_path: Path, db_session, monkeypatch, capsys):
    _seed_supplier(db_session, "SUP-00011", name="CLI Supplier")
    _write_csv(
        tmp_path / "product_master.csv",
        [
            "product_code",
            "product_name",
            "category",
            "unit_of_measure",
            "unit_price",
            "unit_cost",
            "sku_id",
        ],
        [["PRD-10001", "CLI Product", "Electronics", "PCS", "195.0", "150.0", "SKU-000101"]],
    )
    _write_csv(
        tmp_path / "warehouse_master.csv",
        [
            "warehouse_code",
            "warehouse_name",
            "city",
            "state",
            "country",
            "pincode",
            "warehouse_type",
            "warehouse_id",
        ],
        [
            [
                "MAA-01",
                "Chennai Hub",
                "Chennai",
                "Tamil Nadu",
                "India",
                "600001",
                "Regional",
                "WH-MAA-01",
            ]
        ],
    )
    _write_csv(
        tmp_path / "supplier_lead_times.csv",
        [
            "supplier_id",
            "sku_id",
            "average_lead_time_days",
            "minimum_lead_time_days",
            "maximum_lead_time_days",
            "effective_date",
        ],
        [["SUP-00011", "SKU-000101", "5", "3", "8", "2026-01-15"]],
    )

    from tests.conftest import TestingSessionLocal

    monkeypatch.setattr(
        "app.services.client_import_service.SessionLocal",
        TestingSessionLocal,
    )

    exit_dry = cli.main(["import-client-data", "--dry-run", "--staging-dir", str(tmp_path)])
    assert exit_dry == 0
    dry_out = capsys.readouterr().out
    assert "Client data import - DRY RUN" in dry_out
    assert "Added: 1" in dry_out
    assert "No database changes were written." in dry_out
    assert db_session.query(Product).count() == 0

    exit_live = cli.main(["import-client-data", "--staging-dir", str(tmp_path)])
    assert exit_live == 0
    live_out = capsys.readouterr().out
    assert "Client data import - COMPLETED" in live_out
    assert db_session.query(Product).count() == 1
    assert db_session.query(Warehouse).count() == 1
    assert db_session.query(SupplierLeadTime).count() == 1

    _write_csv(
        tmp_path / "product_master.csv",
        [
            "product_code",
            "product_name",
            "category",
            "unit_of_measure",
            "unit_price",
            "unit_cost",
            "sku_id",
        ],
        [["PRD-10002", "Broken Product", "Electronics", "PCS", "10.0", "-5", "SKU-000102"]],
    )
    exit_bad = cli.main(["import-client-data", "--staging-dir", str(tmp_path)])
    assert exit_bad == 1
    assert "Client data import failed" in capsys.readouterr().err
    assert db_session.query(Product).count() == 1


def test_cli_database_error_hides_client_parameters(monkeypatch, capsys):
    def _boom(**_kwargs):
        raise OperationalError(
            "INSERT INTO products (sku_id, name) VALUES (:sku_id, :name)",
            {"sku_id": "SKU-000001", "name": "SecretClientProductXYZ"},
            Exception("value too long"),
        )

    monkeypatch.setattr(cli, "run_client_data_import", _boom)
    exit_code = cli.main(["import-client-data"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "database error (OperationalError)" in captured.err
    assert "No changes were written." in captured.err
    assert "SecretClientProductXYZ" not in captured.err
    assert "INSERT INTO" not in captured.err


def test_missing_staging_dir_fails_clearly(db_session):
    with pytest.raises(ClientImportError, match="does not exist"):
        run_client_data_import(db=db_session, staging_dir="nonexistent_staging_dir")


def test_alembic_008_adds_and_downgrades_client_data_readiness_schema(tmp_path: Path):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    db_file = tmp_path / "m008.db"
    db_url = f"sqlite:///{db_file}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    insp = inspect(engine)
    assert "supplier_lead_times" in set(insp.get_table_names())
    assert {"unit_of_measure", "is_active"} <= {c["name"] for c in insp.get_columns("products")}
    assert {"country", "pincode"} <= {c["name"] for c in insp.get_columns("warehouses")}

    command.downgrade(cfg, "007_create_goods_receipts_tables")
    insp_after = inspect(create_engine(db_url))
    assert "supplier_lead_times" not in set(insp_after.get_table_names())
    assert "unit_of_measure" not in {c["name"] for c in insp_after.get_columns("products")}
    assert "country" not in {c["name"] for c in insp_after.get_columns("warehouses")}


@pytest.mark.parametrize(
    "missing",
    ["minimum_lead_time_days", "maximum_lead_time_days", "effective_date"],
)
def test_lead_time_missing_required_field_fails_and_keeps_stored_values(
    db_session, missing
):
    _seed_supplier(db_session, "SUP-00001")
    dataset = StagingDataset(
        products=[_valid_product("SKU-000001", product_code="PRD-10001")],
        supplier_lead_times=[_valid_lead_time("SUP-00001", "SKU-000001")],
    )
    import_staging_dataset(db_session, dataset)

    partial = _valid_lead_time("SUP-00001", "SKU-000001")
    partial.pop(missing)
    dataset.supplier_lead_times = [partial]

    with pytest.raises(ClientImportValidationError, match=f"missing {missing}"):
        import_staging_dataset(db_session, dataset)

    stored = db_session.get(SupplierLeadTime, ("SUP-00001", "SKU-000001"))
    assert stored.minimum_lead_time_days == 5
    assert stored.maximum_lead_time_days == 15
    assert stored.effective_date == date(2026, 1, 1)


def test_cli_file_read_error_prints_utf8_hint(monkeypatch, capsys):
    def _boom(**_kwargs):
        raise UnicodeDecodeError("utf-8", b"\xe9", 0, 1, "invalid continuation byte")

    monkeypatch.setattr(cli, "run_client_data_import", _boom)
    exit_code = cli.main(["import-client-data"])
    assert exit_code == 1
    assert "could not read staging file" in capsys.readouterr().err


def test_warehouse_missing_type_or_invalid_pincode_fails(db_session):
    bad_pin = _valid_warehouse("WH-BLR-01", pincode="56001")
    with pytest.raises(ClientImportValidationError, match="pincode must be 6 digits"):
        import_staging_dataset(db_session, StagingDataset(warehouses=[bad_pin]))
    assert db_session.query(Warehouse).count() == 0

    no_type = _valid_warehouse("WH-BLR-01")
    no_type.pop("warehouse_type")
    with pytest.raises(
        ClientImportValidationError, match="missing required field 'warehouse_type'"
    ):
        import_staging_dataset(db_session, StagingDataset(warehouses=[no_type]))
    assert db_session.query(Warehouse).count() == 0


def test_blank_primary_column_falls_back_to_canonical_alias(db_session):
    product_with_alias = _valid_product("")
    product_with_alias["canonical_product_id"] = "SKU-000001"
    warehouse_with_alias = _valid_warehouse("")
    warehouse_with_alias["canonical_warehouse_id"] = "WH-BLR-01"

    res = import_staging_dataset(
        db_session,
        StagingDataset(
            products=[product_with_alias],
            warehouses=[warehouse_with_alias],
        ),
    )
    assert res.products.added == 1
    assert res.warehouses.added == 1
    assert db_session.get(Product, "SKU-000001") is not None
    assert db_session.get(Warehouse, "WH-BLR-01") is not None

    empty_both = _valid_product("")
    with pytest.raises(
        ClientImportValidationError, match="empty value for required field 'sku_id'"
    ):
        import_staging_dataset(db_session, StagingDataset(products=[empty_both]))
