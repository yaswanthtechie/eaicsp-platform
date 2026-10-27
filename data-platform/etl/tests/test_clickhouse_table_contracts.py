import os
import re
from pathlib import Path

import pytest

from clickhouse import apply_ddl as ddl

ROOT = Path(__file__).resolve().parents[1]
DDL_DIR = ROOT / "clickhouse"
README = Path(__file__).resolve().parents[3] / "contracts" / "clickhouse" / "README.md"

TABLES = (
    "demand_forecast_history",
    "inventory_snapshots",
    "kpi_metrics",
    "transport_performance",
)


class FakeClient:
    def __init__(self):
        self.commands = []
        self.closed = False

    def command(self, sql):
        self.commands.append(" ".join(sql.split()))

    def close(self):
        self.closed = True


def columns_from_sql(sql):
    match = re.search(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+\S+\s*\((.*?)\)\s*ENGINE",
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    assert match, "Expected one CREATE TABLE definition"
    return {
        name: " ".join(data_type.split())
        for name, data_type in re.findall(
            r"^\s*(\w+)\s+(.+?)(?:,)?\s*$",
            match.group(1),
            re.MULTILINE,
        )
    }


def columns_from_readme(table):
    lines = README.read_text(encoding="utf-8-sig").splitlines()
    start = next(
        (i for i, line in enumerate(lines)
         if line.strip().startswith("## ") and table in line),
        None,
    )
    assert start is not None, f"Missing README section for {table}"

    columns = {}
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if not line.strip().startswith("|"):
            continue

        cells = [
            cell.strip().strip("`")
            for cell in line.strip().strip("|").split("|")
        ]
        if (
            len(cells) < 2
            or cells[0].lower() == "column"
            or all(not cell.strip("-: ") for cell in cells)
        ):
            continue
        columns[cells[0]] = " ".join(cells[1].split())

    return columns


@pytest.mark.parametrize("table", TABLES)
def test_sql_file_has_one_table_and_expected_engine(table):
    sql = (DDL_DIR / f"{table}.sql").read_text(encoding="utf-8-sig")
    assert len(ddl._statements(sql)) == 1
    assert re.search(
        rf"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+{table}\b",
        sql,
        re.IGNORECASE,
    )
    assert "ReplacingMergeTree(version)" in sql
    assert "version DateTime64(3, 'UTC')" in sql


@pytest.mark.parametrize("table", TABLES)
def test_readme_columns_and_types_match_ddl(table):
    sql = (DDL_DIR / f"{table}.sql").read_text(encoding="utf-8-sig")
    sql_columns = columns_from_sql(sql)
    readme_columns = columns_from_readme(table)
    assert readme_columns == sql_columns


def test_partition_columns_are_in_sorting_keys():
    for table, partition_column in (
        ("demand_forecast_history", "batch_date"),
        ("inventory_snapshots", "snapshot_date"),
        ("kpi_metrics", "metric_date"),
    ):
        sql = (DDL_DIR / f"{table}.sql").read_text(encoding="utf-8-sig")
        order = re.search(r"ORDER\s+BY\s*\((.*?)\)", sql, re.IGNORECASE)
        assert order and partition_column in order.group(1)

    transport = (DDL_DIR / "transport_performance.sql").read_text(encoding="utf-8-sig")
    assert "PARTITION BY tuple()" in transport
    assert "ORDER BY (shipment_id)" in transport


def test_apply_ddl_uses_fake_client_and_is_repeatable(monkeypatch):
    monkeypatch.setenv("CLICKHOUSE_DB", "unit_test_analytics")
    monkeypatch.delenv("CLICKHOUSE_DATABASE", raising=False)
    client = FakeClient()

    first = ddl.apply_ddl(client=client)
    first_commands = list(client.commands)
    second = ddl.apply_ddl(client=client)

    assert first == second == [f"{table}.sql" for table in TABLES]
    assert len(first_commands) == 5  # database + four tables
    assert len(client.commands) == 10
    assert client.commands[0] == "CREATE DATABASE IF NOT EXISTS `unit_test_analytics`"
    for table in TABLES:
        assert any(f"`unit_test_analytics`.`{table}`" in command for command in client.commands)


def test_database_environment_variable_fallback(monkeypatch):
    monkeypatch.delenv("CLICKHOUSE_DB", raising=False)
    monkeypatch.setenv("CLICKHOUSE_DATABASE", "fallback_analytics")
    assert ddl._database() == "fallback_analytics"


def test_missing_password_fails_loudly(monkeypatch):
    monkeypatch.delenv("CLICKHOUSE_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="CLICKHOUSE_PASSWORD"):
        ddl._client()


@pytest.mark.integration
def test_live_clickhouse_has_four_tables():
    host = os.getenv("CLICKHOUSE_HOST")
    if not host:
        pytest.skip("Set CLICKHOUSE_HOST to enable ClickHouse integration test")

    client = ddl._client()
    try:
        ddl.apply_ddl(client=client)
        database = ddl._database()
        result = client.query(
            "SELECT name FROM system.tables "
            "WHERE database = {database:String} "
            "AND name IN {tables:Array(String)}",
            parameters={"database": database, "tables": list(TABLES)},
        )
        assert set(row[0] for row in result.result_rows) == set(TABLES)
    finally:
        client.close()
