"""Incremental ClickHouse sink for the dbt marts (R12-13 M2).

PostgreSQL + dbt stay the source of truth; ClickHouse is the read-optimised
copy the dashboard's historical charts query.

Design notes
------------
* One ClickHouse table per mart, ``ReplacingMergeTree(version)``. Re-loading a
  row (same ORDER BY key) replaces the older version, so loads are idempotent.
* Dashboards read the ``<database>.<mart>`` VIEW, which is ``SELECT ... FINAL``
  so un-merged duplicates are never visible.
* ReplacingMergeTree only de-duplicates *within a partition*. A table whose
  ORDER BY key does not contain the partition column therefore must NOT be
  partitioned by that column. ``mart_inventory_position`` is keyed by
  (sku_id, warehouse_id), so it is unpartitioned; partitioning it by
  snapshot month would keep a stale row per month.
* Incremental: per-mart watermark (``clickhouse_<mart>`` in ``etl_watermark``,
  the same table/logic the Postgres load uses). The watermark only advances
  after ClickHouse has accepted the insert. We re-read
  ``CLICKHOUSE_LOOKBACK_DAYS`` (default 3) before the watermark so late-arriving
  corrections are picked up; the replacing engine makes the overlap harmless.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text

from database import get_engine
from watermark import get_watermark, update_watermark

logger = logging.getLogger(__name__)

PG_SCHEMA = os.getenv("ANALYTICS_PG_SCHEMA", "analytics")

MARTS = {
    "mart_daily_sales_by_warehouse": {
        "date_column": "sale_date",
        "columns": ["sale_date", "warehouse_id", "sales_rows", "units_sold", "sales_amount"],
        "ddl": """
            sale_date Date,
            warehouse_id String,
            sales_rows UInt64,
            units_sold Int64,
            sales_amount Decimal(18, 2)
        """,
        "order_by": "(sale_date, warehouse_id)",
        "partition_by": "toYYYYMM(sale_date)",
    },
    "mart_daily_shipments_by_warehouse": {
        "date_column": "shipment_date",
        "columns": ["shipment_date", "warehouse_id", "shipment_rows", "units_shipped"],
        "ddl": """
            shipment_date Date,
            warehouse_id String,
            shipment_rows UInt64,
            units_shipped Int64
        """,
        "order_by": "(shipment_date, warehouse_id)",
        "partition_by": "toYYYYMM(shipment_date)",
    },
    "mart_inventory_position": {
        "date_column": "snapshot_date",
        "columns": ["snapshot_date", "sku_id", "warehouse_id", "quantity_on_hand"],
        "ddl": """
            snapshot_date Date,
            sku_id String,
            warehouse_id String,
            quantity_on_hand Int64
        """,
        "order_by": "(sku_id, warehouse_id)",
        "partition_by": "tuple()",  # see module docstring
    },
}


def _database() -> str:
    return os.getenv("CLICKHOUSE_DATABASE", "analytics")


def _target(mart: str) -> str:
    return f"ch_{mart}"


def _client():
    import clickhouse_connect

    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        connect_timeout=5,
        send_receive_timeout=60,
    )


def ensure_schema(client) -> None:
    db = _database()
    client.command(f"CREATE DATABASE IF NOT EXISTS {db}")
    for mart, spec in MARTS.items():
        client.command(f"""
            CREATE TABLE IF NOT EXISTS {db}.{_target(mart)} (
                {spec['ddl']},
                version DateTime64(3, 'UTC')
            )
            ENGINE = ReplacingMergeTree(version)
            PARTITION BY {spec['partition_by']}
            ORDER BY {spec['order_by']}
        """)
        client.command(
            f"CREATE VIEW IF NOT EXISTS {db}.{mart} AS "
            f"SELECT * FROM {db}.{_target(mart)} FINAL"
        )


def _normalise(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.date()
    return value


def to_ch_rows(mart: str, rows, version: datetime) -> list[list]:
    """Map Postgres mapping-rows to positional ClickHouse rows (+ version)."""
    cols = MARTS[mart]["columns"]
    return [[_normalise(r[c]) for c in cols] + [version] for r in rows]


def _lookback_start(watermark) -> date:
    days = int(os.getenv("CLICKHOUSE_LOOKBACK_DAYS", "3"))
    if isinstance(watermark, datetime):
        watermark = watermark.date()
    return watermark - timedelta(days=days)


def sync_marts(client=None, engine=None) -> dict:
    """Incrementally copy every mart to ClickHouse.

    ``client``/``engine`` are injectable for tests. Raises on ClickHouse
    failure *without* advancing that mart's watermark, so the next run retries
    the same window (Airflow retries the task).
    """
    owns_client = client is None
    client = client or _client()
    engine = engine or get_engine()
    db = _database()
    results: dict = {}
    try:
        ensure_schema(client)
        for mart, spec in MARTS.items():
            wm_name = f"clickhouse_{mart}"
            start = _lookback_start(get_watermark(wm_name))
            query = text(
                f"SELECT {', '.join(spec['columns'])} "
                f"FROM {PG_SCHEMA}.{mart} "
                f"WHERE {spec['date_column']} >= :start "
                f"ORDER BY {spec['date_column']}"
            )
            with engine.connect() as conn:
                rows = conn.execute(query, {"start": start}).mappings().all()

            if not rows:
                results[mart] = {"rows": 0, "watermark": None}
                continue

            data = to_ch_rows(mart, rows, datetime.now(timezone.utc))
            client.insert(
                f"{db}.{_target(mart)}",
                data,
                column_names=spec["columns"] + ["version"],
            )

            latest = max(_normalise(r[spec["date_column"]]) for r in rows)
            update_watermark(latest, wm_name)  # only after a successful insert
            results[mart] = {"rows": len(rows), "watermark": str(latest)}
            logger.info("ClickHouse %s: %d rows, watermark=%s", mart, len(rows), latest)
        return results
    finally:
        if owns_client:
            client.close()
