import csv
from datetime import date
from pathlib import Path

import pytest

from etl.src import kpi_metrics as metrics
from clickhouse import load_seed_stock


class FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class FakeClient:
    def __init__(self, query_results=None):
        self.query_results = query_results or {}
        self.queries = []
        self.inserts = []

    def query(self, sql):
        self.queries.append(sql)
        for view, rows in self.query_results.items():
            if f".`{view}`" in sql:
                return FakeResult(rows)
        return FakeResult([])

    def insert(self, table, rows, column_names, database):
        self.inserts.append({
            "table": table,
            "rows": list(rows),
            "column_names": list(column_names),
            "database": database,
        })


def test_refresh_writes_warehouse_and_overall_metrics():
    client = FakeClient({
        "kpi_stockouts_by_warehouse": [
            ("WH-A", 3),
            ("WH-B", 5),
        ],
        "kpi_open_pos_by_status": [
            ("WH-A", 2),
            ("WH-B", 4),
        ],
        "kpi_fill_rate_by_warehouse": [
            ("WH-A", 8, 10),
            ("WH-B", 9, 20),
        ],
        "kpi_on_time_delivery_by_warehouse": [
            ("WH-A", 9, 10),
            ("WH-B", 15, 20),
        ],
    })

    count = metrics.refresh_kpi_metrics(
        client, "analytics", metric_date=date(2026, 10, 14)
    )

    assert count == 12
    insert = client.inserts[0]
    assert insert["table"] == "kpi_metrics"
    assert insert["database"] == "analytics"

    rows = insert["rows"]
    lookup = {(r[1], r[2]): r[4] for r in rows}
    assert lookup[("stockout_count", "WH-A")] == 3.0
    assert lookup[("stockout_count", "WH-B")] == 5.0
    assert lookup[("stockout_count", "")] == 8.0
    assert lookup[("open_pos", "")] == 6.0
    assert lookup[("fill_rate", "WH-A")] == 80.0
    assert lookup[("fill_rate", "WH-B")] == 45.0
    assert lookup[("fill_rate", "")] == pytest.approx(17 / 30 * 100, abs=0.01)
    assert lookup[("on_time_delivery_pct", "")] == pytest.approx(24 / 30 * 100, abs=0.01)

    assert all(r[0] == date(2026, 10, 14) for r in rows)
    assert all(r[3] == "" for r in rows)


def test_empty_views_write_no_rows():
    client = FakeClient()
    count = metrics.refresh_kpi_metrics(client, "analytics")
    assert count == 0
    assert client.inserts == []
    assert len(client.queries) == 4


def test_zero_denominator_is_skipped():
    client = FakeClient({
        "kpi_fill_rate_by_warehouse": [("WH-A", 0, 0)],
        "kpi_on_time_delivery_by_warehouse": [("WH-A", 0, 0)],
    })

    metrics.refresh_kpi_metrics(client, "analytics")

    if client.inserts:
        rows = [row for insert in client.inserts for row in insert["rows"]]
    else:
        rows = []
    assert not any(
        row[1] in {"fill_rate", "on_time_delivery_pct"}
        for row in rows
    )


def test_seed_loader_reads_current_stock_csv(tmp_path):
    csv_path = tmp_path / "current_stock.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "snapshot_date",
                "sku_id",
                "warehouse_id",
                "quantity_on_hand",
            ],
        )
        writer.writeheader()
        writer.writerow({
            "snapshot_date": "2026-10-14",
            "sku_id": "SKU-1",
            "warehouse_id": "WH-A",
            "quantity_on_hand": "0",
        })
        writer.writerow({
            "snapshot_date": "2026-10-14",
            "sku_id": "SKU-2",
            "warehouse_id": "WH-A",
            "quantity_on_hand": "7",
        })

    client = FakeClient()
    count = load_seed_stock.load_current_stock(client, "analytics", tmp_path)

    assert count == 2
    insert = client.inserts[0]
    assert insert["table"] == "inventory_snapshots"
    assert insert["column_names"] == list(load_seed_stock.COLUMNS)
    assert (str(insert["rows"][0][0]), *insert["rows"][0][1:5]) == (
        "2026-10-14", "SKU-1", "WH-A", 0, "seed"
    )


def test_seed_loader_requires_current_stock_csv(tmp_path):
    with pytest.raises(FileNotFoundError, match="current_stock.csv"):
        load_seed_stock.load_current_stock(FakeClient(), "analytics", tmp_path)
