import csv
from datetime import date

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
            ("WH-BLR-01", 3),
            ("WH-BOM-01", 5),
        ],
        "kpi_open_pos_by_status": [
            ("WH-BLR-01", 2),
            ("WH-BOM-01", 4),
        ],
        "kpi_fill_rate_by_warehouse": [
            ("WH-BLR-01", 8, 10),
            ("WH-BOM-01", 9, 20),
        ],
        "kpi_on_time_delivery_by_warehouse": [
            ("WH-BLR-01", 9, 10),
            ("WH-BOM-01", 15, 20),
        ],
    })

    count = metrics.refresh_kpi_metrics(
        client, "analytics", metric_date=date(2026, 10, 14)
    )

    assert count == 12
    insert = client.inserts[0]
    assert insert["table"] == "kpi_metrics"
    assert insert["database"] == "analytics"
    assert insert["column_names"] == list(metrics.COLUMNS)

    rows = insert["rows"]
    lookup = {(r[1], r[2]): r[4] for r in rows}
    assert lookup[("stockout_count", "WH-BLR-01")] == 3.0
    assert lookup[("stockout_count", "WH-BOM-01")] == 5.0
    assert lookup[("stockout_count", "")] == 8.0
    assert lookup[("open_pos", "")] == 6.0
    assert lookup[("fill_rate", "WH-BLR-01")] == 80.0
    assert lookup[("fill_rate", "WH-BOM-01")] == 45.0
    # Weighted: 17 of 30 lines = 56.67%, not the average of 80% and 45%.
    assert lookup[("fill_rate", "")] == 56.67
    assert lookup[("on_time_delivery_pct", "")] == 80.0
    assert all(r[0] == date(2026, 10, 14) for r in rows)
    assert all(r[3] == "" for r in rows)


def test_empty_views_write_no_rows():
    client = FakeClient()
    count = metrics.refresh_kpi_metrics(client, "analytics")
    assert count == 0
    assert client.inserts == []
    assert len(client.queries) == 4


def test_zero_denominator_writes_no_rate_row():
    client = FakeClient({
        "kpi_fill_rate_by_warehouse": [("WH-BLR-01", 0, 0)],
        "kpi_on_time_delivery_by_warehouse": [("WH-BLR-01", 0, 0)],
    })

    assert metrics.refresh_kpi_metrics(client, "analytics") == 0
    assert client.inserts == []


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
            "sku_id": "SKU-000007",
            "warehouse_id": "WH-CCU-01",
            "quantity_on_hand": "0",
        })
        writer.writerow({
            "snapshot_date": "2026-10-14",
            "sku_id": "SKU-000029",
            "warehouse_id": "WH-DEL-01",
            "quantity_on_hand": "144",
        })

    client = FakeClient()
    count = load_seed_stock.load_current_stock(client, "analytics", tmp_path)

    assert count == 2
    insert = client.inserts[0]
    assert insert["table"] == "inventory_snapshots"
    assert insert["database"] == "analytics"
    assert insert["column_names"] == list(load_seed_stock.COLUMNS)
    assert insert["rows"][0][:5] == (
        date(2026, 10, 14), "SKU-000007", "WH-CCU-01", 0, "seed"
    )


def test_seed_loader_requires_current_stock_csv(tmp_path):
    with pytest.raises(FileNotFoundError, match="current_stock.csv"):
        load_seed_stock.load_current_stock(FakeClient(), "analytics", tmp_path)


def test_seed_loader_rejects_csv_without_required_columns(tmp_path):
    (tmp_path / "current_stock.csv").write_text(
        "snapshot_date,sku_id,warehouse_id\n2026-10-14,SKU-000007,WH-CCU-01\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="quantity_on_hand"):
        load_seed_stock.load_current_stock(FakeClient(), "analytics", tmp_path)