"""Apply the four ClickHouse table contracts idempotently."""
import os
import re
import sys
from pathlib import Path

DDL_DIR = Path(__file__).resolve().parent
TABLE_FILES = (
    "demand_forecast_history.sql",
    "inventory_snapshots.sql",
    "kpi_metrics.sql",
    "transport_performance.sql",
)
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _database():
    return os.getenv("CLICKHOUSE_DB") or os.getenv("CLICKHOUSE_DATABASE") or "analytics"


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
        raise ValueError("Each table SQL file must contain exactly one statement.")
    return statements


def apply_ddl(client=None):
    database = _database()
    if not IDENTIFIER.fullmatch(database):
        raise ValueError(f"Invalid ClickHouse database identifier: {database!r}")

    owns_client = client is None
    if owns_client:
        client = _client()

    try:
        client.command(f"CREATE DATABASE IF NOT EXISTS `{database}`")
        applied = []

        for filename in TABLE_FILES:
            table = Path(filename).stem
            path = DDL_DIR / filename
            (statement,) = _statements(path.read_text(encoding="utf-8-sig"))

            pattern = r"(?i)^(CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+)" + re.escape(table) + r"\b"
            qualified_statement, count = re.subn(
                pattern,
                rf"\1`{database}`.`{table}`",
                statement,
                count=1,
            )
            if count != 1:
                raise ValueError(f"{filename} must define table {table} with CREATE TABLE IF NOT EXISTS.")

            client.command(qualified_statement)
            applied.append(filename)
            print(f"Applied {filename}")

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

    print(f"Successfully applied {len(applied)} ClickHouse table definitions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
