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

    def command(self, sql, parameters=None):
        self.commands.append((sql, parameters))

    def insert(self, table, rows, **kwargs):
        self.inserts.append((table, rows, kwargs))


@pytest.fixture(scope="module")
def valid_sample_rows():
    sample_dir = Path(loader.__file__).parent / "samples" / "client_format"
    spec_path = Path(loader.__file__).with_name("spec.yaml")
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))

    known = {
        entity: set()
        for entity, _ in loader.MASTER_KEYS.values()
    }
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


def test_daily_sales_aggregates_quantity_and_revenue():
    rows = [
        {
            "sale_date": "2026-01-10",
            "sku_id": "SKU-1",
            "warehouse_id": "WH-1",
            "quantity_sold": 2,
            "sales_amount": 20,
        },
        {
            "sale_date": "2026-01-10",
            "sku_id": "SKU-1",
            "warehouse_id": "WH-1",
            "quantity_sold": 3,
            "sales_amount": 45,
        },
    ]
    assert kpi.calculate_daily_sales(rows) == [
        (date(2026, 1, 10), "SKU-1", "WH-1", 5, 65.0)
    ]


def test_stock_cover_uses_exact_28_day_window():
    snapshot = date(2026, 1, 28)
    inventory = [{
        "snapshot_date": snapshot.isoformat(),
        "sku_id": "SKU-1",
        "warehouse_id": "WH-1",
        "quantity_on_hand": 280,
    }]

    sales = [
        (snapshot - timedelta(days=27), "SKU-1", "WH-1", 10, 10.0),
        (snapshot - timedelta(days=28), "SKU-1", "WH-1", 100, 100.0),
        (snapshot + timedelta(days=1), "SKU-1", "WH-1", 100, 100.0),
        (snapshot - timedelta(days=1), "SKU-1", "WH-2", 100, 100.0),
    ]

    result = kpi.calculate_stock_cover(inventory, sales)

    assert result == [
        (snapshot, "SKU-1", "WH-1", 280, 0.3571, 784.0)
    ]


def test_zero_sales_returns_null_stock_cover():
    inventory = [{
        "snapshot_date": "2026-01-28",
        "sku_id": "SKU-1",
        "warehouse_id": "WH-1",
        "quantity_on_hand": 100,
    }]
    result = kpi.calculate_stock_cover(inventory, [])
    assert result[0][4] == 0
    assert result[0][5] is None


def test_supplier_on_time_excludes_cancelled_orders():
    rows = [
        {
            "po_status": "Received",
            "received_date": "2026-01-10",
            "expected_date": "2026-01-10",
            "supplier_id": "SUP-1",
        },
        {
            "po_status": "Received",
            "received_date": "2026-01-12",
            "expected_date": "2026-01-10",
            "supplier_id": "SUP-1",
        },
        {
            "po_status": "Cancelled",
            "received_date": "2026-01-10",
            "expected_date": "2026-01-10",
            "supplier_id": "SUP-1",
        },
    ]
    assert kpi.calculate_supplier_on_time(rows) == [
        (date(2026, 1, 1), "SUP-1", 2, 1, 50.0)
    ]


def test_sales_sample_passes_loader_validation(valid_sample_rows):
    accepted, rejected = valid_sample_rows
    rows = accepted["sales_history"]

    assert rows
    assert len(rows) + len(rejected["sales_history"]) > 0

    canonical = [
        {
            **row,
            "sku_id": row["product_code"],
            "warehouse_id": row["warehouse_code"],
        }
        for row in rows
    ]
    result = kpi.calculate_daily_sales(canonical)

    assert result
    assert all(item[3] >= 0 for item in result)


def test_inventory_sample_passes_loader_validation(valid_sample_rows):
    accepted, rejected = valid_sample_rows
    rows = accepted["inventory_snapshot"]

    assert rows
    assert len(rows) + len(rejected["inventory_snapshot"]) > 0

    canonical = [
        {
            **row,
            "sku_id": row["product_code"],
            "warehouse_id": row["warehouse_code"],
        }
        for row in rows
    ]
    result = kpi.calculate_stock_cover(canonical, [])

    assert len(result) == len(rows)
    assert all(item[4] == 0 and item[5] is None for item in result)


def test_purchase_order_sample_passes_loader_validation(valid_sample_rows):
    accepted, rejected = valid_sample_rows
    rows = accepted["purchase_order_history"]

    assert rows
    assert len(rows) + len(rejected["purchase_order_history"]) > 0

    canonical = [
        {**row, "supplier_id": row["supplier_code"]}
        for row in rows
    ]
    result = kpi.calculate_supplier_on_time(canonical)

    received = [
        row for row in rows
        if row.get("po_status", "").strip().lower() == "received"
        and row.get("received_date")
        and row.get("expected_date")
    ]

    assert sum(item[2] for item in result) == len(received)


def test_kpi_build_repeats_delete_then_insert_for_all_tables(monkeypatch):
    records = {
        "sales_history": [{
            "sale_date": "2026-01-10",
            "sku_id": "SKU-1",
            "warehouse_id": "WH-1",
            "quantity_sold": 5,
            "sales_amount": 50,
        }],
        "inventory_snapshot": [{
            "snapshot_date": "2026-01-10",
            "sku_id": "SKU-1",
            "warehouse_id": "WH-1",
            "quantity_on_hand": 100,
        }],
        "purchase_order_history": [{
            "po_status": "Received",
            "received_date": "2026-01-10",
            "expected_date": "2026-01-10",
            "supplier_id": "SUP-1",
        }],
    }

    monkeypatch.setattr(
        kpi,
        "_records",
        lambda engine, entity: iter(records[entity]),
    )

    client = FakeClient()

    first = kpi.build_client_kpis(None, client, "analytics")
    first_operations = list(client.commands), list(client.inserts)

    second = kpi.build_client_kpis(None, client, "analytics")
    second_operations = (
        client.commands[len(first_operations[0]):],
        client.inserts[len(first_operations[1]):],
    )

    expected_tables = [
        "client_daily_sales",
        "client_stock_cover",
        "client_supplier_on_time",
    ]

    assert first == second
    assert first == {table: 1 for table in expected_tables}

    for commands, inserts in (first_operations, second_operations):
        assert len(commands) == 3
        assert len(inserts) == 3

        assert [item[0] for item in inserts] == expected_tables

        for (sql, parameters), table in zip(commands, expected_tables):
            assert f"`analytics`.`{table}`" in sql
            assert "IN %(dates)s" in sql
            assert parameters is not None
            assert len(parameters["dates"]) == 1
            assert isinstance(parameters["dates"][0], date)

        for command_index, insert_index in zip(
            range(len(commands)), range(len(inserts))
        ):
            assert command_index == insert_index


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
