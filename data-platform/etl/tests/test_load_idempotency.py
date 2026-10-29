"""Test bulk_upsert idempotency using in-memory SQLite."""
import re
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

import etl.src.load as load
from etl.src.load import bulk_upsert

pytestmark = pytest.mark.skipif(
    sqlite3.sqlite_version_info < (3, 39),
    reason="needs SQLite 3.39+ for IS DISTINCT FROM",
)

COLUMNS = [
    "date", "sku_id", "warehouse_id", "quantity_sold", "unit_price",
    "source_batch", "run_id", "pipeline_version",
]
KEYS = ["date", "sku_id", "warehouse_id"]


@pytest.fixture
def engine():
    engine = create_engine("sqlite://", poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _add_now(dbapi_connection, _record):
        dbapi_connection.create_function("NOW", 0, lambda: "T1")

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE sales_fact (
                id INTEGER PRIMARY KEY,
                date TEXT, sku_id TEXT, warehouse_id TEXT,
                quantity_sold INTEGER, unit_price REAL,
                source_batch TEXT, run_id INTEGER, pipeline_version TEXT,
                loaded_at TEXT DEFAULT 'T0', updated_at TEXT DEFAULT 'T0',
                UNIQUE (date, sku_id, warehouse_id)
            )
        """))
    yield engine
    engine.dispose()


def _records(run_id, quantities):
    return [
        {
            "date": "2026-10-14",
            "sku_id": f"SKU-00000{i}",
            "warehouse_id": "WH-BLR-01",
            "quantity_sold": qty,
            "unit_price": 10.0,
            "source_batch": "sales_daily.csv",
            "run_id": run_id,
            "pipeline_version": "1.0.0",
        }
        for i, qty in enumerate(quantities, start=1)
    ]


def _upsert(engine, records):
    return bulk_upsert(engine, "sales_fact", COLUMNS, KEYS, records)


def _rows(engine):
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT sku_id, quantity_sold, run_id FROM sales_fact ORDER BY sku_id"
        )).fetchall()


def test_first_load_counts_inserts(engine):
    assert _upsert(engine, _records(1, [5, 5, 5])) == (3, 0)
    assert len(_rows(engine)) == 3


def test_identical_second_run_changes_nothing(engine):
    _upsert(engine, _records(1, [5, 5, 5]))
    before = _rows(engine)

    assert _upsert(engine, _records(2, [5, 5, 5])) == (0, 0)
    assert _rows(engine) == before


def test_changed_row_counts_as_update(engine):
    _upsert(engine, _records(1, [5, 5, 5]))

    assert _upsert(engine, _records(2, [9, 5, 5])) == (0, 1)
    assert _rows(engine)[0] == ("SKU-000001", 9, 2)


def test_zero_quantity_change_is_an_update_not_skipped(engine):
    _upsert(engine, _records(1, [5]))

    assert _upsert(engine, _records(2, [0])) == (0, 1)
    assert _rows(engine)[0][1] == 0


def test_new_and_changed_rows_in_one_run(engine):
    _upsert(engine, _records(1, [5, 5]))

    assert _upsert(engine, _records(2, [7, 5, 5])) == (1, 1)


def test_load_data_reads_the_column_its_query_returns(monkeypatch):
    class _Conn:
        def execute(self, query, params=None):
            sql = str(query)
            if "INSERT INTO sales_fact_history" in sql:
                return None
            alias = re.search(r"RETURNING\s+.+?\s+AS\s+(\w+)", sql, re.S).group(1)
            return SimpleNamespace(
                fetchone=lambda: SimpleNamespace(**{alias: True})
            )

    class _Begin:
        def __enter__(self):
            return _Conn()

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(
        load, "get_engine", lambda: SimpleNamespace(begin=lambda: _Begin())
    )
    frame = pd.DataFrame(_records(1, [5, 5])).drop(
        columns=["source_batch", "run_id", "pipeline_version"]
    )

    inserted, updated = load.load_data(
        [{"data": frame, "file_path": Path("sales_daily.csv")}], run_id=1
    )

    assert (inserted, updated) == (2, 0)
