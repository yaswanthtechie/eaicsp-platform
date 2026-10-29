"""M2 - ClickHouse sink. Docker-free: fake ClickHouse client + fake Postgres engine."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

import clickhouse_sink as cs


class FakeClient:
    def __init__(self, fail_insert=False, fail_command=False):
        self.commands, self.inserts = [], []
        self.fail_insert, self.fail_command, self.closed = fail_insert, fail_command, False

    def command(self, sql):
        if self.fail_command:
            raise ConnectionError("clickhouse unreachable")
        self.commands.append(" ".join(sql.split()))

    def insert(self, table, data, column_names=None):
        if self.fail_insert:
            raise RuntimeError("insert rejected")
        self.inserts.append({"table": table, "data": data, "columns": column_names})

    def close(self):
        self.closed = True


class FakeEngine:
    """Returns canned rows per mart and records the query parameters."""
    def __init__(self, data):
        self.data, self.calls = data, []

    def connect(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, query, params):
        sql = str(query)
        mart = next(m for m in cs.MARTS if f".{m} " in sql or sql.endswith(m))
        self.calls.append({"mart": mart, "sql": sql, "params": params})
        rows = self.data.get(mart, [])
        return type("R", (), {"mappings": lambda s: type("M", (), {"all": lambda s2: rows})()})()


@pytest.fixture
def watermarks(monkeypatch):
    store = {}
    monkeypatch.setattr(cs, "get_watermark", lambda name: store.get(name, date(1900, 1, 1)))
    monkeypatch.setattr(cs, "update_watermark", lambda d, name: store.__setitem__(name, d))
    return store


SALES = [
    {"sale_date": date(2024, 1, 1), "warehouse_id": "WH1", "sales_rows": 3, "units_sold": 10,
     "sales_amount": Decimal("99.50")},
    {"sale_date": date(2024, 1, 2), "warehouse_id": "WH1", "sales_rows": 1, "units_sold": 2,
     "sales_amount": Decimal("5.00")},
]


def test_rows_are_mapped_by_column_name_with_version_appended():
    v = datetime(2026, 9, 29, tzinfo=timezone.utc)
    out = cs.to_ch_rows("mart_daily_sales_by_warehouse", SALES, v)
    assert out[0] == [date(2024, 1, 1), "WH1", 3, 10, 99.5, v]


def test_first_run_loads_everything_and_advances_watermark_to_latest_date(watermarks):
    client, engine = FakeClient(), FakeEngine({"mart_daily_sales_by_warehouse": SALES})

    res = cs.sync_marts(client=client, engine=engine)

    assert res["mart_daily_sales_by_warehouse"] == {"rows": 2, "watermark": "2024-01-02"}
    assert watermarks["clickhouse_mart_daily_sales_by_warehouse"] == date(2024, 1, 2)
    (ins,) = client.inserts
    assert ins["table"].endswith("ch_mart_daily_sales_by_warehouse")
    assert ins["columns"][-1] == "version" and len(ins["data"]) == 2


def test_second_run_is_incremental_reading_from_watermark_minus_lookback(watermarks, monkeypatch):
    monkeypatch.setenv("CLICKHOUSE_LOOKBACK_DAYS", "3")
    watermarks["clickhouse_mart_daily_sales_by_warehouse"] = date(2024, 1, 10)
    engine = FakeEngine({})

    cs.sync_marts(client=FakeClient(), engine=engine)

    call = next(c for c in engine.calls if c["mart"] == "mart_daily_sales_by_warehouse")
    assert call["params"]["start"] == date(2024, 1, 7)      # not 1900-01-01: no full reload


def test_failed_insert_raises_and_does_not_advance_watermark(watermarks):
    client = FakeClient(fail_insert=True)
    engine = FakeEngine({"mart_daily_sales_by_warehouse": SALES})

    with pytest.raises(RuntimeError, match="insert rejected"):
        cs.sync_marts(client=client, engine=engine)

    assert "clickhouse_mart_daily_sales_by_warehouse" not in watermarks   # retry re-reads same window


def test_empty_marts_insert_nothing_and_leave_watermarks_alone(watermarks):
    client = FakeClient()
    res = cs.sync_marts(client=client, engine=FakeEngine({}))
    assert client.inserts == [] and watermarks == {}
    assert all(v == {"rows": 0, "watermark": None} for v in res.values())


def test_clickhouse_unreachable_raises_and_advances_nothing(watermarks):
    with pytest.raises(ConnectionError):
        cs.sync_marts(client=FakeClient(fail_command=True), engine=FakeEngine({"mart_daily_sales_by_warehouse": SALES}))
    assert watermarks == {}


def test_injected_client_is_not_closed_by_sync(watermarks):
    client = FakeClient()
    cs.sync_marts(client=client, engine=FakeEngine({}))
    assert client.closed is False


def test_reloading_same_rows_twice_is_safe_because_table_is_replacing_by_version(watermarks):
    client = FakeClient()
    engine = FakeEngine({"mart_daily_sales_by_warehouse": SALES})
    cs.sync_marts(client=client, engine=engine)
    cs.sync_marts(client=client, engine=engine)
    ddl = [c for c in client.commands if "ch_mart_daily_sales_by_warehouse (" in c][0]
    assert "ReplacingMergeTree(version)" in ddl
    assert len(client.inserts) == 2          # overlap is intentional; the engine collapses it


def test_inventory_table_is_not_partitioned_so_replacing_can_dedupe_across_months():
    client = FakeClient()
    cs.ensure_schema(client)
    inv = [c for c in client.commands if "ch_mart_inventory_position (" in c][0]
    assert "PARTITION BY tuple()" in inv and "ORDER BY (sku_id, warehouse_id)" in inv
    sales = [c for c in client.commands if "ch_mart_daily_sales_by_warehouse (" in c][0]
    assert "PARTITION BY toYYYYMM(sale_date)" in sales


def test_dashboard_views_are_created_in_the_analytics_database_and_use_final():
    client = FakeClient()
    cs.ensure_schema(client)
    views = [c for c in client.commands if c.startswith("CREATE VIEW")]
    assert len(views) == 3
    for mart in cs.MARTS:
        assert any(f"analytics.{mart} AS SELECT * FROM analytics.ch_{mart} FINAL" in v for v in views)
