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
    "purchase_orders",
    "po_lines",
    "goods_receipt_lines",
)

VIEWS = (
    "kpi_stockouts_by_warehouse",
    "kpi_open_pos_by_status",
    "kpi_fill_rate_by_warehouse",
    "kpi_on_time_delivery_by_warehouse",
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
        (
            i for i, line in enumerate(lines)
            if line.strip().startswith("## ") and table in line
        ),
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
    assert columns_from_readme(table) == columns_from_sql(sql)


def test_partition_columns_are_in_sorting_keys():
    for table, partition_column in (
        ("demand_forecast_history", "batch_date"),
        ("inventory_snapshots", "snapshot_date"),
        ("kpi_metrics", "metric_date"),
    ):
        sql = (DDL_DIR / f"{table}.sql").read_text(encoding="utf-8-sig")
        order = re.search(r"ORDER\s+BY\s*\((.*?)\)", sql, re.IGNORECASE)
        assert order and partition_column in order.group(1)

    for table, expected_order in (
        ("purchase_orders", "(po_id)"),
        ("po_lines", "(po_id, line_number)"),
        ("goods_receipt_lines", "(receipt_id, sku_id)"),
    ):
        sql = (DDL_DIR / f"{table}.sql").read_text(encoding="utf-8-sig")
        assert "PARTITION BY tuple()" in sql
        assert f"ORDER BY {expected_order}" in sql

    transport = (DDL_DIR / "transport_performance.sql").read_text(
        encoding="utf-8-sig"
    )
    assert "PARTITION BY tuple()" in transport
    assert "ORDER BY (shipment_id)" in transport


def test_apply_ddl_uses_fake_client_and_is_repeatable(monkeypatch):
    monkeypatch.setenv("CLICKHOUSE_DB", "unit_test_analytics")
    monkeypatch.delenv("CLICKHOUSE_DATABASE", raising=False)
    client = FakeClient()

    first = ddl.apply_ddl(client=client)
    first_commands = list(client.commands)
    second = ddl.apply_ddl(client=client)

    expected = [f"{table}.sql" for table in TABLES]
    expected += [f"views/{view}.sql" for view in VIEWS]

    assert first == second == expected
    assert len(first_commands) == 12  # database + 7 tables + 4 views
    assert len(client.commands) == 24
    assert first_commands[0] == (
        "CREATE DATABASE IF NOT EXISTS `unit_test_analytics`"
    )

    # All table definitions must be applied before any view.
    view_command_indices = [
        i for i, command in enumerate(first_commands)
        if "CREATE OR REPLACE VIEW" in command
    ]
    table_command_indices = [
        i for i, command in enumerate(first_commands)
        if "CREATE TABLE IF NOT EXISTS" in command
    ]
    assert max(table_command_indices) < min(view_command_indices)

    for table in TABLES:
        assert any(
            f"`unit_test_analytics`.`{table}`" in command
            for command in first_commands
        )

    for view in VIEWS:
        assert any(
            f"VIEW `unit_test_analytics`.{view}" in command
            for command in first_commands
        )


@pytest.mark.parametrize("view", VIEWS)
def test_view_sql_has_one_statement_and_database_placeholder(view):
    path = DDL_DIR / "views" / f"{view}.sql"
    sql = path.read_text(encoding="utf-8-sig")
    assert len(ddl._statements(sql)) == 1

    statement = ddl._view_statement(f"{view}.sql", "test_analytics")
    assert statement.startswith(
        f"CREATE OR REPLACE VIEW `test_analytics`.{view}"
    )
    assert "{db}" not in statement


def test_bad_view_filename_definition_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(ddl, "VIEW_DIR", tmp_path)
    (tmp_path / "kpi_stockouts_by_warehouse.sql").write_text(
        "CREATE OR REPLACE VIEW {db}.wrong_view AS SELECT 1;",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must define view"):
        ddl._view_statement("kpi_stockouts_by_warehouse.sql", "analytics")


def test_contract_readme_documents_all_views_and_event_tables():
    readme = README.read_text(encoding="utf-8-sig")
    for table in ("purchase_orders", "po_lines", "goods_receipt_lines"):
        assert f"## " in readme
        assert table in readme

    assert "## 8. KPI views" in readme
    for view in VIEWS:
        assert view in readme

    assert "## Schema notes" in readme
    assert "inventory snapshot schema adds `source` and `version`" in readme


def test_database_environment_variable_fallback(monkeypatch):
    monkeypatch.delenv("CLICKHOUSE_DB", raising=False)
    monkeypatch.setenv("CLICKHOUSE_DATABASE", "fallback_analytics")
    assert ddl._database() == "fallback_analytics"


def test_missing_password_fails_loudly(monkeypatch):
    monkeypatch.delenv("CLICKHOUSE_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="CLICKHOUSE_PASSWORD"):
        ddl._client()


@pytest.mark.integration
def test_live_clickhouse_has_contract_tables_and_views():
    if not os.getenv("CLICKHOUSE_HOST"):
        pytest.skip("Set CLICKHOUSE_HOST to enable ClickHouse integration test")

    client = ddl._client()
    try:
        ddl.apply_ddl(client=client)
        database = ddl._database()

        table_result = client.query(
            "SELECT name FROM system.tables "
            "WHERE database = {database:String} "
            "AND name IN {tables:Array(String)}",
            parameters={"database": database, "tables": list(TABLES)},
        )
        assert {row[0] for row in table_result.result_rows} == set(TABLES)

        view_result = client.query(
            "SELECT name FROM system.tables "
            "WHERE database = {database:String} "
            "AND name IN {views:Array(String)}",
            parameters={"database": database, "views": list(VIEWS)},
        )
        assert {row[0] for row in view_result.result_rows} == set(VIEWS)
    finally:
        client.close()
