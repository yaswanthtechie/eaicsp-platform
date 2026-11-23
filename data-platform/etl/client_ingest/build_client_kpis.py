"""Build client dashboard KPIs from canonical PostgreSQL staging records."""

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ETL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ETL_DIR / "etl" / "src"))
sys.path.insert(0, str(ETL_DIR))
sys.path.insert(0, str(ETL_DIR / "clickhouse"))
from database import get_engine
from sqlalchemy import text

from apply_ddl import IDENTIFIER, _client, _database


DAILY_COLUMNS = (
    "sale_date", "sku_id", "warehouse_id", "units_sold",
    "revenue", "computed_at", "version",
)
STOCK_COLUMNS = (
    "snapshot_date", "sku_id", "warehouse_id", "quantity_on_hand",
    "average_daily_sales", "stock_cover_days", "computed_at", "version",
)
SUPPLIER_COLUMNS = (
    "metric_month", "supplier_id", "received_pos", "on_time_pos",
    "on_time_pct", "computed_at", "version",
)


def _records(engine, entity_type):
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT canonical_record
            FROM client_ingest_staging
            WHERE entity_type = :entity
            ORDER BY id
        """), {"entity": entity_type})

        for (record,) in result:
            if isinstance(record, str):
                record = json.loads(record)
            yield record


def _date(value):
    return date.fromisoformat(str(value)[:10])


def calculate_daily_sales(records):
    totals = defaultdict(lambda: [0, 0.0])

    for row in records:
        key = (
            _date(row["sale_date"]),
            row["sku_id"],
            row["warehouse_id"],
        )
        quantity = int(row["quantity_sold"])
        revenue = float(
            row.get("sales_amount")
            or quantity * float(row.get("unit_price") or 0)
        )
        totals[key][0] += quantity
        totals[key][1] += revenue

    return [
        (day, sku, warehouse, units, round(revenue, 2))
        for (day, sku, warehouse), (units, revenue)
        in sorted(totals.items())
    ]


def calculate_stock_cover(inventory_records, daily_sales):
    sales_by_key = defaultdict(dict)

    for day, sku, warehouse, units, _ in daily_sales:
        sales_by_key[(sku, warehouse)][day] = units

    output = []
    for row in inventory_records:
        snapshot = _date(row["snapshot_date"])
        sku = row["sku_id"]
        warehouse = row["warehouse_id"]
        on_hand = int(row["quantity_on_hand"])

        start = snapshot - timedelta(days=27)
        units = sum(
            quantity
            for day, quantity in sales_by_key[(sku, warehouse)].items()
            if start <= day <= snapshot
        )
        average = units / 28.0
        cover = on_hand / average if average > 0 else None

        output.append((
            snapshot, sku, warehouse, on_hand,
            round(average, 4),
            round(cover, 2) if cover is not None else None,
        ))

    return output


def calculate_supplier_on_time(records):
    totals = defaultdict(lambda: [0, 0])

    for row in records:
        if str(row.get("po_status", "")).strip().lower() != "received":
            continue
        if not row.get("received_date") or not row.get("expected_date"):
            continue

        received = _date(row["received_date"])
        expected = _date(row["expected_date"])
        supplier = row["supplier_id"]
        month = received.replace(day=1)

        totals[(month, supplier)][0] += 1
        if received <= expected:
            totals[(month, supplier)][1] += 1

    output = []
    for (month, supplier), (received, on_time) in sorted(totals.items()):
        percentage = 100.0 * on_time / received if received else None
        output.append((
            month, supplier, received, on_time,
            round(percentage, 2) if percentage is not None else None,
        ))

    return output


def _replace_dates(client, database, table, column, values):
    """Delete existing rows for these dates using bound date parameters."""
    for name in (database, table, column):
        if not IDENTIFIER.fullmatch(name):
            raise ValueError(f"Invalid ClickHouse identifier: {name!r}")

    dates = tuple(sorted(set(values)))
    if not dates:
        return

    client.command(
        f"ALTER TABLE `{database}`.`{table}` DELETE "
        f"WHERE `{column}` IN %(dates)s SETTINGS mutations_sync = 1",
        parameters={"dates": dates},
    )

def build_client_kpis(engine, client, database):
    """Calculate and insert all client KPI snapshots."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    sales = calculate_daily_sales(_records(engine, "sales_history"))
    stock = calculate_stock_cover(
        _records(engine, "inventory_snapshot"), sales
    )
    supplier = calculate_supplier_on_time(
        _records(engine, "purchase_order_history")
    )

    if sales:
        _replace_dates(client, database, "client_daily_sales", "sale_date", [row[0] for row in sales])
        client.insert(
            "client_daily_sales",
            [(*row, now, now) for row in sales],
            column_names=list(DAILY_COLUMNS),
            database=database,
        )

    if stock:
        _replace_dates(client, database, "client_stock_cover", "snapshot_date", [row[0] for row in stock])
        client.insert(
            "client_stock_cover",
            [(*row, now, now) for row in stock],
            column_names=list(STOCK_COLUMNS),
            database=database,
        )

    if supplier:
        _replace_dates(client, database, "client_supplier_on_time", "metric_month", [row[0] for row in supplier])
        client.insert(
            "client_supplier_on_time",
            [(*row, now, now) for row in supplier],
            column_names=list(SUPPLIER_COLUMNS),
            database=database,
        )

    counts = {
        "client_daily_sales": len(sales),
        "client_stock_cover": len(stock),
        "client_supplier_on_time": len(supplier),
    }
    return counts


def main():
    from dotenv import load_dotenv
    load_dotenv(ETL_DIR / ".env")

    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()

    client = None
    try:
        client = _client()
        counts = build_client_kpis(get_engine(), client, _database())
        for table, count in counts.items():
            print(f"{table}: {count} rows")
        return 0
    except Exception as exc:
        print(f"ERROR building client KPIs: {exc}", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
