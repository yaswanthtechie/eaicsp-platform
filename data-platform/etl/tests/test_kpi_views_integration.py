"""The four KPI views on a real ClickHouse, with expected outputs.

Stockouts run on the seed's current_stock.csv. The other three KPIs have no
seed data (POs and shipments only exist as Flow B events), so they run on
fixture rows built from the contract examples in contracts/events/examples/
(PO-2026-000123, SUP-00045, SKU-000123, WH-BLR-01, GR-2026-000077,
SHP-2026-000077), using canonical IDs only.

Needs CLICKHOUSE_HOST and CLICKHOUSE_PASSWORD (e.g. the ETL docker compose).
Each test gets its own throwaway database and drops it afterwards.
"""
import os
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

SEED_DIR = Path(__file__).resolve().parents[2] / "out"
T1 = "2026-10-15 10:00:00"
T2 = "2026-10-16 10:00:00"

PO_COLUMNS = [
    "po_id", "supplier_id", "warehouse_id", "status", "total_amount",
    "currency", "approved_at", "status_changed_at", "version",
]


@pytest.fixture
def kpi_db(monkeypatch):
    if not os.getenv("CLICKHOUSE_HOST"):
        pytest.skip("Set CLICKHOUSE_HOST to enable ClickHouse integration tests")

    from clickhouse import apply_ddl

    database = "analytics_kpi_test_" + uuid.uuid4().hex[:8]
    monkeypatch.setenv("CLICKHOUSE_DB", database)
    client = apply_ddl._client()
    try:
        apply_ddl.apply_ddl(client)
        yield client, database
    finally:
        try:
            client.command(f"DROP DATABASE IF EXISTS `{database}`")
        finally:
            client.close()


def _rows(client, database, sql):
    return client.query(sql.replace("{db}", f"`{database}`")).result_rows


def test_seed_stockout_view(kpi_db):
    from clickhouse.load_seed_stock import load_current_stock

    client, database = kpi_db
    if not (SEED_DIR / "current_stock.csv").is_file():
        pytest.skip("Run `make seed` first (needs data-platform/out/current_stock.csv)")

    assert load_current_stock(client, database, SEED_DIR) == 3000

    rows = _rows(client, database, """
        SELECT warehouse_id, stockout_count, total_skus, toString(as_of_date)
        FROM {db}.kpi_stockouts_by_warehouse
        ORDER BY warehouse_id
    """)
    assert rows == [
        ("WH-BLR-01", 6, 500, "2026-10-14"),
        ("WH-BOM-01", 14, 500, "2026-10-14"),
        ("WH-CCU-01", 10, 500, "2026-10-14"),
        ("WH-DEL-01", 8, 500, "2026-10-14"),
        ("WH-HYD-01", 8, 500, "2026-10-14"),
        ("WH-MAA-01", 9, 500, "2026-10-14"),
    ]

    # Loading the same seed again must not double-count.
    load_current_stock(client, database, SEED_DIR)
    total = _rows(client, database, """
        SELECT sum(stockout_count), sum(total_skus)
        FROM {db}.kpi_stockouts_by_warehouse
    """)
    assert total == [(55, 3000)]


def test_open_po_view_uses_each_pos_latest_status(kpi_db):
    client, database = kpi_db
    client.insert(
        "purchase_orders",
        [
            # Contract example: approved, then received -> closed.
            ("PO-2026-000123", "SUP-00045", "WH-BLR-01", "approved", 45000.0, "INR", T1, T1, T1),
            ("PO-2026-000123", "SUP-00045", "WH-BLR-01", "received", 45000.0, "INR", T1, T2, T2),
            # Approved, then dispatched: only its latest status counts.
            ("PO-2026-000124", "SUP-00045", "WH-BLR-01", "approved", 12000.0, "INR", T1, T1, T1),
            ("PO-2026-000124", "SUP-00045", "WH-BLR-01", "in_transit", 12000.0, "INR", T1, T2, T2),
            ("PO-2026-000125", "SUP-00007", "WH-DEL-01", "acknowledged", 8000.0, "INR", T1, T1, T1),
            ("PO-2026-000126", "SUP-00007", "WH-DEL-01", "approved", 5000.0, "INR", T1, T1, T1),
        ],
        column_names=PO_COLUMNS,
        database=database,
    )

    rows = _rows(client, database, """
        SELECT warehouse_id, status, open_po_count, open_po_value
        FROM {db}.kpi_open_pos_by_status
        ORDER BY warehouse_id, status
    """)
    assert rows == [
        ("WH-BLR-01", "in_transit", 1, 12000.0),
        ("WH-DEL-01", "acknowledged", 1, 8000.0),
        ("WH-DEL-01", "approved", 1, 5000.0),
    ]


def test_fill_rate_view_counts_lines_received_in_full(kpi_db):
    client, database = kpi_db
    client.insert(
        "po_lines",
        [
            ("PO-2026-000123", 1, "SKU-000123", "WH-BLR-01", 100, T1),
            ("PO-2026-000123", 2, "SKU-000124", "WH-BLR-01", 50, T1),
            ("PO-2026-000124", 1, "SKU-000200", "WH-BLR-01", 10, T1),
            ("PO-2026-000127", 1, "SKU-000300", "WH-DEL-01", 40, T1),
        ],
        column_names=[
            "po_id", "line_number", "sku_id", "warehouse_id",
            "quantity_ordered", "version",
        ],
        database=database,
    )
    client.insert(
        "goods_receipt_lines",
        [
            ("GR-2026-000077", "PO-2026-000123", "SKU-000123", "WH-BLR-01", 100, T2, T2),
            ("GR-2026-000077", "PO-2026-000123", "SKU-000124", "WH-BLR-01", 30, T2, T2),
            ("GR-2026-000078", "PO-2026-000127", "SKU-000300", "WH-DEL-01", 40, T2, T2),
        ],
        column_names=[
            "receipt_id", "po_id", "sku_id", "warehouse_id",
            "quantity_received", "received_at", "version",
        ],
        database=database,
    )

    rows = _rows(client, database, """
        SELECT warehouse_id, total_lines_ordered, lines_fulfilled, fill_rate
        FROM {db}.kpi_fill_rate_by_warehouse
        ORDER BY warehouse_id
    """)
    assert rows == [
        ("WH-BLR-01", 2, 1, 50.0),
        ("WH-DEL-01", 1, 1, 100.0),
    ]


def test_on_time_delivery_view_counts_only_delivered_shipments(kpi_db):
    client, database = kpi_db
    client.insert(
        "transport_performance",
        [
            ("SHP-2026-000077", "PO-2026-000123", "SUP-00045", "WH-BLR-01", "BlueDart",
             "2026-10-15 08:00:00", "2026-10-16 08:00:00", "2026-10-16 07:00:00", 1, 0.0,
             "2026-10-16 07:00:00"),
            ("SHP-2026-000078", "PO-2026-000127", "SUP-00007", "WH-DEL-01", "BlueDart",
             "2026-10-15 08:00:00", "2026-10-16 08:00:00", "2026-10-16 10:00:00", 0, 2.0,
             "2026-10-16 10:00:00"),
            ("SHP-2026-000080", "PO-2026-000128", "SUP-00045", "WH-BLR-01", "BlueDart",
             "2026-10-15 08:00:00", "2026-10-16 08:00:00", "2026-10-16 07:30:00", 1, 0.0,
             "2026-10-16 07:30:00"),
            # Still in transit: not delivered, so not counted.
            ("SHP-2026-000079", "PO-2026-000124", "SUP-00045", "WH-BLR-01", "BlueDart",
             "2026-10-15 08:00:00", "2026-10-16 08:00:00", None, None, None,
             "2026-10-15 08:00:00"),
        ],
        column_names=[
            "shipment_id", "po_id", "supplier_id", "warehouse_id", "carrier",
            "dispatched_at", "predicted_eta", "delivered_at", "on_time",
            "delay_hours", "version",
        ],
        database=database,
    )

    rows = _rows(client, database, """
        SELECT warehouse_id, total_shipments, delivered_on_time, delayed, on_time_delivery_pct
        FROM {db}.kpi_on_time_delivery_by_warehouse
        ORDER BY warehouse_id
    """)
    assert rows == [
        ("WH-BLR-01", 2, 2, 0, 100.0),
        ("WH-DEL-01", 1, 0, 1, 0.0),
    ]
