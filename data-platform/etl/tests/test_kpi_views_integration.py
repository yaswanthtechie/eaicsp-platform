"""Integration tests for the four dashboard KPI views."""

import os
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def kpi_db():
    if not os.getenv("CLICKHOUSE_HOST"):
        pytest.skip("Set CLICKHOUSE_HOST to enable ClickHouse integration tests")

    from clickhouse import apply_ddl

    original_db = os.environ.get("CLICKHOUSE_DB")
    test_db = "analytics_kpi_test_" + uuid.uuid4().hex[:8]
    os.environ["CLICKHOUSE_DB"] = test_db
    client = None

    try:
        client = apply_ddl._client()
        apply_ddl.apply_ddl(client)

        yield client, test_db

    finally:
        if client is not None:
            try:
                client.command(f"DROP DATABASE IF EXISTS `{test_db}`")
            finally:
                client.close()

        if original_db is None:
            os.environ.pop("CLICKHOUSE_DB", None)
        else:
            os.environ["CLICKHOUSE_DB"] = original_db


def test_seed_stockout_view(kpi_db):
    from clickhouse.load_seed_stock import load_current_stock

    client, database = kpi_db
    etl_root = Path(__file__).resolve().parents[1]
    seed_dir = etl_root.parent / "out"

    assert (seed_dir / "current_stock.csv").exists()

    load_current_stock(client, database, seed_dir)

    result = client.query(
        f"""
        SELECT sum(stockout_count), sum(total_skus)
        FROM `{database}`.`kpi_stockouts_by_warehouse`
        """
    ).result_rows[0]

    assert result[0] == 55
    assert result[1] == 3000


def test_open_po_view(kpi_db):
    client, database = kpi_db

    client.insert(
        "purchase_orders",
        [
            ("PO-A", "SUP-A", "WH-BLR-01", "approved", 12000.0,
             "INR", "2026-10-15 10:00:00", "2026-10-15 10:00:00",
             "2026-10-15 10:00:00"),
            ("PO-B", "SUP-B", "WH-DEL-01", "acknowledged", 8000.0,
             "INR", "2026-10-15 10:00:00", "2026-10-15 10:00:00",
             "2026-10-15 10:00:00"),
            ("PO-C", "SUP-C", "WH-DEL-01", "approved", 5000.0,
             "INR", "2026-10-15 10:00:00", "2026-10-15 10:00:00",
             "2026-10-15 10:00:00"),
            ("PO-D", "SUP-D", "WH-BLR-01", "closed", 4000.0,
             "INR", "2026-10-15 10:00:00", "2026-10-16 10:00:00",
             "2026-10-16 10:00:00"),
        ],
        column_names=[
            "po_id", "supplier_id", "warehouse_id", "status", "total_amount",
            "currency", "approved_at", "status_changed_at", "version",
        ],
        database=database,
    )

    rows = client.query(
        f"""
        SELECT warehouse_id, status, open_po_count, open_po_value
        FROM `{database}`.`kpi_open_pos_by_status`
        ORDER BY warehouse_id, status
        """
    ).result_rows

    actual = {(r[0], r[1]): (r[2], r[3]) for r in rows}

    assert actual == {
        ("WH-BLR-01", "approved"): (1, 12000.0),
        ("WH-DEL-01", "acknowledged"): (1, 8000.0),
        ("WH-DEL-01", "approved"): (1, 5000.0),
    }


def test_fill_rate_view(kpi_db):
    client, database = kpi_db

    client.insert(
        "purchase_orders",
        [
            ("PO-F1", "SUP-A", "WH-BLR-01", "closed", 100.0,
             "INR", "2026-10-15 10:00:00", "2026-10-16 10:00:00",
             "2026-10-16 10:00:00"),
            ("PO-F2", "SUP-B", "WH-DEL-01", "closed", 100.0,
             "INR", "2026-10-15 10:00:00", "2026-10-16 10:00:00",
             "2026-10-16 10:00:00"),
        ],
        column_names=[
            "po_id", "supplier_id", "warehouse_id", "status", "total_amount",
            "currency", "approved_at", "status_changed_at", "version",
        ],
        database=database,
    )

    client.insert(
        "po_lines",
        [
            ("PO-F1", 1, "SKU-1", "WH-BLR-01", 100, "2026-10-16 10:00:00"),
            ("PO-F1", 2, "SKU-2", "WH-BLR-01", 50, "2026-10-16 10:00:00"),
            ("PO-F2", 1, "SKU-3", "WH-DEL-01", 40, "2026-10-16 10:00:00"),
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
            ("GR-1", "PO-F1", "SKU-1", "WH-BLR-01", 100,
             "2026-10-16 10:00:00", "2026-10-16 10:00:00"),
            ("GR-2", "PO-F1", "SKU-2", "WH-BLR-01", 30,
             "2026-10-16 10:00:00", "2026-10-16 10:00:00"),
            ("GR-3", "PO-F2", "SKU-3", "WH-DEL-01", 40,
             "2026-10-16 10:00:00", "2026-10-16 10:00:00"),
        ],
        column_names=[
            "receipt_id", "po_id", "sku_id", "warehouse_id",
            "quantity_received", "received_at", "version",
        ],
        database=database,
    )

    rows = client.query(
        f"""
        SELECT warehouse_id, total_lines_ordered, lines_fulfilled, fill_rate
        FROM `{database}`.`kpi_fill_rate_by_warehouse`
        ORDER BY warehouse_id
        """
    ).result_rows

    actual = {r[0]: (r[1], r[2], r[3]) for r in rows}

    assert actual["WH-BLR-01"] == (2, 1, 50.0)
    assert actual["WH-DEL-01"] == (1, 1, 100.0)


def test_on_time_delivery_view(kpi_db):
    client, database = kpi_db

    client.insert(
        "transport_performance",
        [
            ("S-1", "PO-1", "SUP-A", "WH-BLR-01", "C1",
             "2026-10-15 08:00:00", "2026-10-16 08:00:00",
             "2026-10-16 07:00:00", 1, 0.0, "2026-10-16 07:00:00"),
            ("S-2", "PO-2", "SUP-B", "WH-DEL-01", "C2",
             "2026-10-15 08:00:00", "2026-10-16 08:00:00",
             "2026-10-16 10:00:00", 0, 2.0, "2026-10-16 10:00:00"),
            ("S-3", "PO-3", "SUP-C", "WH-BLR-01", "C1",
             "2026-10-15 08:00:00", "2026-10-16 08:00:00",
             "2026-10-16 07:30:00", 1, 0.0, "2026-10-16 07:30:00"),
        ],
        column_names=[
            "shipment_id", "po_id", "supplier_id", "warehouse_id", "carrier",
            "dispatched_at", "predicted_eta", "delivered_at", "on_time",
            "delay_hours", "version",
        ],
        database=database,
    )

    rows = client.query(
        f"""
        SELECT warehouse_id, total_shipments, delivered_on_time,
               delayed, on_time_delivery_pct
        FROM `{database}`.`kpi_on_time_delivery_by_warehouse`
        ORDER BY warehouse_id
        """
    ).result_rows

    actual = {r[0]: r[1:] for r in rows}

    assert actual["WH-BLR-01"] == (2, 2, 0, 100.0)
    assert actual["WH-DEL-01"] == (1, 0, 1, 0.0)
