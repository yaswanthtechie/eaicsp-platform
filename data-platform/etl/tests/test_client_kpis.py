import csv
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

import client_ingest.load_client_data as loader
import client_ingest.build_client_kpis as kpi


class FakeClient:
    def __init__(self):
        self.commands = []
        self.inserts = []
        self.operations = []

    def command(self, sql, parameters=None):
        self.commands.append((sql, parameters))
        table = next(
            name
            for name in (
                "client_daily_sales",
                "client_stock_cover",
                "client_supplier_on_time",
            )
            if f"`analytics`.`{name}`" in sql
        )
        self.operations.append(("delete", table, sql, parameters))

    def insert(self, table, rows, **kwargs):
        self.inserts.append((table, rows, kwargs))
        self.operations.append(("insert", table, rows, kwargs))


@pytest.fixture(scope="module")
def valid_sample_rows():
    sample_dir = Path(loader.__file__).parent / "samples" / "client_format"
    spec_path = Path(loader.__file__).with_name("spec.yaml")
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))

    known = {entity: set() for entity, _ in loader.MASTER_KEYS.values()}
    accepted = defaultdict(list)
    rejected = defaultdict(list)

    for key in loader.ORDER:
        path = sample_dir / f"{key}.csv"
        if not path.exists():
            continue

        rules = spec["files"][key]["columns"]
        seen = set()

        with path.open(newline="", encoding="utf-8-sig") as handle:
            for raw in csv.DictReader(handle):

                def capture(row):
                    accepted[key].append(dict(row))

                errors = loader.process_unique_row(
                    seen, key, raw, rules, known, capture
                )
                if errors:
                    rejected[key].append(errors)

    return accepted, rejected


def canonical_maps(accepted):
    """Assign deterministic canonical IDs to the synthetic client master codes."""
    product_codes = sorted(row["product_code"] for row in accepted["product_master"])
    supplier_codes = sorted(row["supplier_code"] for row in accepted["supplier_master"])

    product_ids = {
        code: f"SKU-{123 + index:06d}" for index, code in enumerate(product_codes)
    }
    supplier_ids = {
        code: f"SUP-{44 + index:05d}" for index, code in enumerate(supplier_codes)
    }
    # The synthetic sample uses one warehouse per city, with suffix -01.
    warehouse_ids = {
        row["warehouse_code"]: f"WH-{row['warehouse_code'].split('-')[0]}-01"
        for row in accepted["warehouse_master"]
    }

    return product_ids, warehouse_ids, supplier_ids


def canonicalize_rows(rows, product_ids, warehouse_ids, supplier_ids):
    result = []

    for row in rows:
        item = dict(row)

        if item.get("product_code"):
            item["sku_id"] = product_ids[item["product_code"]]

        if item.get("warehouse_code"):
            item["warehouse_id"] = warehouse_ids[item["warehouse_code"]]

        if item.get("supplier_code"):
            item["supplier_id"] = supplier_ids[item["supplier_code"]]

        result.append(item)

    return result


def test_daily_sales_aggregates_quantity_and_revenue():
    rows = [
        {
            "sale_date": "2026-01-10",
            "sku_id": "SKU-000123",
            "warehouse_id": "WH-BLR-01",
            "quantity_sold": 2,
            "sales_amount": 20,
        },
        {
            "sale_date": "2026-01-10",
            "sku_id": "SKU-000123",
            "warehouse_id": "WH-BLR-01",
            "quantity_sold": 3,
            "sales_amount": 45,
        },
    ]

    assert kpi.calculate_daily_sales(rows) == [
        (date(2026, 1, 10), "SKU-000123", "WH-BLR-01", 5, 65.0)
    ]


def test_stock_cover_uses_exact_28_day_window():
    snapshot = date(2026, 1, 28)
    inventory = [
        {
            "snapshot_date": snapshot.isoformat(),
            "sku_id": "SKU-000123",
            "warehouse_id": "WH-BLR-01",
            "quantity_on_hand": 280,
        }
    ]

    sales = [
        (snapshot - timedelta(days=27), "SKU-000123", "WH-BLR-01", 10, 10.0),
        (snapshot - timedelta(days=28), "SKU-000123", "WH-BLR-01", 100, 100.0),
        (snapshot + timedelta(days=1), "SKU-000123", "WH-BLR-01", 100, 100.0),
        (snapshot - timedelta(days=1), "SKU-000123", "WH-HYD-01", 100, 100.0),
    ]

    result = kpi.calculate_stock_cover(inventory, sales)

    assert result == [(snapshot, "SKU-000123", "WH-BLR-01", 280, 0.3571, 784.0)]


def test_zero_sales_returns_null_stock_cover():
    inventory = [
        {
            "snapshot_date": "2026-01-28",
            "sku_id": "SKU-000123",
            "warehouse_id": "WH-BLR-01",
            "quantity_on_hand": 100,
        }
    ]

    result = kpi.calculate_stock_cover(inventory, [])

    assert result[0][4] == 0
    assert result[0][5] is None


def test_supplier_on_time_excludes_cancelled_orders():
    rows = [
        {
            "po_status": "Received",
            "received_date": "2026-01-10",
            "expected_date": "2026-01-10",
            "supplier_id": "SUP-00045",
        },
        {
            "po_status": "Received",
            "received_date": "2026-01-12",
            "expected_date": "2026-01-10",
            "supplier_id": "SUP-00045",
        },
        {
            "po_status": "Cancelled",
            "received_date": "2026-01-10",
            "expected_date": "2026-01-10",
            "supplier_id": "SUP-00045",
        },
    ]

    assert kpi.calculate_supplier_on_time(rows) == [
        (date(2026, 1, 1), "SUP-00045", 2, 1, 50.0)
    ]


def test_sales_sample_passes_loader_validation(valid_sample_rows):
    accepted, _ = valid_sample_rows
    product_ids, warehouse_ids, supplier_ids = canonical_maps(accepted)

    assert product_ids["PRD-10482"] == "SKU-000123"
    assert product_ids["PRD-10492"] == "SKU-000133"
    assert warehouse_ids["BLR-01"] == "WH-BLR-01"
    assert supplier_ids["SUP-2232"] == "SUP-00045"

    rows = accepted["sales_history"]
    assert rows

    canonical = canonicalize_rows(rows, product_ids, warehouse_ids, supplier_ids)
    result = kpi.calculate_daily_sales(canonical)

    assert len(result) == 27450

    expected = (
        date(2025, 5, 10),
        "SKU-000123",
        "WH-BLR-01",
        8,
        34992.0,
    )

    assert expected in result
    assert all(item[1].startswith("SKU-") for item in result)
    assert all(item[2].startswith("WH-") for item in result)


def test_inventory_sample_passes_loader_validation(valid_sample_rows):
    accepted, _ = valid_sample_rows
    product_ids, warehouse_ids, supplier_ids = canonical_maps(accepted)

    inventory_rows = accepted["inventory_snapshot"]
    sales_rows = accepted["sales_history"]

    assert inventory_rows

    inventory = canonicalize_rows(
        inventory_rows, product_ids, warehouse_ids, supplier_ids
    )
    sales = canonicalize_rows(sales_rows, product_ids, warehouse_ids, supplier_ids)

    daily_sales = kpi.calculate_daily_sales(sales)
    result = kpi.calculate_stock_cover(inventory, daily_sales)

    expected = (
        date(2026, 11, 9),
        "SKU-000123",
        "WH-BLR-01",
        896,
        10.2857,
        87.11,
    )
    assert expected in result
    assert len(result) == len(inventory_rows)

    no_sales_sku = product_ids["PRD-10492"]
    no_sales_row = next(
        item
        for item in result
        if item[0] == date(2026, 11, 9)
        and item[1] == no_sales_sku
        and item[2] == "WH-BLR-01"
    )
    assert no_sales_row[4] == 0
    assert no_sales_row[5] is None


def test_purchase_order_sample_passes_loader_validation(valid_sample_rows):
    accepted, _ = valid_sample_rows
    product_ids, warehouse_ids, supplier_ids = canonical_maps(accepted)

    rows = accepted["purchase_order_history"]
    assert rows

    canonical = canonicalize_rows(rows, product_ids, warehouse_ids, supplier_ids)
    result = kpi.calculate_supplier_on_time(canonical)

    assert sum(item[2] for item in result) == 338
    assert (
        date(2025, 12, 1),
        "SUP-00045",
        2,
        1,
        50.0,
    ) in result


def test_kpi_build_repeats_delete_then_insert_for_all_tables(monkeypatch):
    records = {
        "sales_history": [
            {
                "sale_date": "2026-01-10",
                "sku_id": "SKU-000123",
                "warehouse_id": "WH-BLR-01",
                "quantity_sold": 5,
                "sales_amount": 50,
            }
        ],
        "inventory_snapshot": [
            {
                "snapshot_date": "2026-01-10",
                "sku_id": "SKU-000123",
                "warehouse_id": "WH-BLR-01",
                "quantity_on_hand": 100,
            }
        ],
        "purchase_order_history": [
            {
                "po_status": "Received",
                "received_date": "2026-01-10",
                "expected_date": "2026-01-10",
                "supplier_id": "SUP-00045",
            }
        ],
    }

    monkeypatch.setattr(
        kpi,
        "_records",
        lambda engine, entity: iter(records[entity]),
    )

    client = FakeClient()

    first = kpi.build_client_kpis(None, client, "analytics")
    first_operations = list(client.operations)

    second = kpi.build_client_kpis(None, client, "analytics")
    second_operations = client.operations[len(first_operations) :]

    expected_tables = [
        "client_daily_sales",
        "client_stock_cover",
        "client_supplier_on_time",
    ]
    expected_operations = [
        (operation, table)
        for table in expected_tables
        for operation in ("delete", "insert")
    ]

    assert first == second
    assert first == {table: 1 for table in expected_tables}

    for operations in (first_operations, second_operations):
        assert [(item[0], item[1]) for item in operations] == (expected_operations)

        for operation in operations:
            if operation[0] == "delete":
                _, table, sql, parameters = operation
                assert f"`analytics`.`{table}`" in sql
                assert "IN %(dates)s" in sql
                assert parameters is not None
                assert len(parameters["dates"]) == 1
                assert isinstance(parameters["dates"][0], date)


def test_invalid_database_identifier_fails_before_sql():
    client = FakeClient()

    with pytest.raises(ValueError, match="Invalid ClickHouse identifier"):
        kpi._replace_dates(
            client,
            "bad-database",
            "client_daily_sales",
            "sale_date",
            [date(2026, 1, 10)],
        )

    assert client.commands == []
    assert client.operations == []
