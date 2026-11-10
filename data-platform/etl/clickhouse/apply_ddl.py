"""Apply ClickHouse table contracts and KPI views idempotently."""
import os
import re
import sys
from pathlib import Path

DDL_DIR = Path(__file__).resolve().parent
VIEW_DIR = DDL_DIR / "views"

TABLE_FILES = (
    "demand_forecast_history.sql",
    "inventory_snapshots.sql",
    "kpi_metrics.sql",
    "transport_performance.sql",
    "purchase_orders.sql",
    "po_lines.sql",
    "goods_receipt_lines.sql",
)

VIEW_FILES = (
    "kpi_stockouts_by_warehouse.sql",
    "kpi_open_pos_by_status.sql",
    "kpi_fill_rate_by_warehouse.sql",
    "kpi_on_time_delivery_by_warehouse.sql",
)

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _database():
    return (
        os.getenv("CLICKHOUSE_DB")
        or os.getenv("CLICKHOUSE_DATABASE")
        or "analytics"
    )


def _client():
    import clickhouse_connect

    password = os.getenv("CLICKHOUSE_PASSWORD")
    if not password:
        raise ValueError("CLICKHOUSE_PASSWORD must be set.")

    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=password,
        connect_timeout=5,
        send_receive_timeout=60,
    )


def _statements(sql):
    statements = [part.strip() for part in sql.split(";") if part.strip()]
    if len(statements) != 1:
        raise ValueError("Each SQL file must contain exactly one statement.")
    return statements


def _table_statement(filename, database):
    table = Path(filename).stem
    path = DDL_DIR / filename
    (statement,) = _statements(path.read_text(encoding="utf-8-sig"))

    pattern = (
        r"(?i)^CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+"
        + re.escape(table)
        + r"\b"
    )
    qualified, count = re.subn(
        pattern,
        f"CREATE TABLE IF NOT EXISTS `{database}`.`{table}`",
        statement,
        count=1,
        flags=re.IGNORECASE,
    )
    if count != 1:
        raise ValueError(
            f"{filename} must define table {table} "
            "with CREATE TABLE IF NOT EXISTS."
        )
    return qualified


def _view_statement(filename, database):
    view = Path(filename).stem
    path = VIEW_DIR / filename
    (statement,) = _statements(path.read_text(encoding="utf-8-sig"))

    pattern = (
        r"(?i)^CREATE\s+OR\s+REPLACE\s+VIEW\s+\{db\}\."
        + re.escape(view)
        + r"\b"
    )
    if not re.match(pattern, statement):
        raise ValueError(
            f"{filename} must define view {view} "
            "with CREATE OR REPLACE VIEW {db}.<view_name>."
        )

    return statement.replace("{db}", f"`{database}`")


def apply_ddl(client=None):
    database = _database()
    if not IDENTIFIER.fullmatch(database):
        raise ValueError(
            f"Invalid ClickHouse database identifier: {database!r}"
        )

    owns_client = client is None
    if owns_client:
        client = _client()

    try:
        client.command(f"CREATE DATABASE IF NOT EXISTS `{database}`")
        applied = []

        for filename in TABLE_FILES:
            client.command(_table_statement(filename, database))
            applied.append(filename)
            print(f"Applied {filename}")

        for filename in VIEW_FILES:
            client.command(_view_statement(filename, database))
            applied.append(f"views/{filename}")
            print(f"Applied views/{filename}")

        return applied
    finally:
        if owns_client:
            client.close()


def main():
    try:
        applied = apply_ddl()
    except Exception as exc:
        print(f"ERROR applying ClickHouse DDL: {exc}", file=sys.stderr)
        return 1

    print(
        f"Successfully applied {len(applied)} "
        f"ClickHouse tables and views."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
