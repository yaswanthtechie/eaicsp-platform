import os

import pandas as pd
import pytest

from spark.sales_backfill import month_bounds, month_list, validate_month

COLS = ["date", "sku_id", "warehouse_id", "quantity_sold", "unit_price"]


# ---------- pure tests: no Spark / Docker ----------
def test_month_list_is_restartable_by_month():
    assert list(month_list("2024-01", "2024-03")) == ["2024-01", "2024-02", "2024-03"]
    assert list(month_list("2024-05", "2024-05")) == ["2024-05"]
    assert list(month_list("2024-11", "2025-02")) == ["2024-11", "2024-12", "2025-01", "2025-02"]


def test_month_bounds_handles_december_rollover():
    assert month_bounds("2024-12") == ("2024-12-01", "2025-01-01")
    assert month_bounds("2024-02") == ("2024-02-01", "2024-03-01")


@pytest.mark.parametrize("bad", ["2024-13", "2024-1", "24-01", "2024-01; rm -rf /", "", None])
def test_invalid_month_rejected(bad):
    with pytest.raises(ValueError):
        validate_month(bad)


def test_reversed_range_rejected():
    with pytest.raises(ValueError):
        list(month_list("2024-06", "2024-01"))


# ---------- Spark tests: need pyspark + Java ----------
@pytest.fixture(scope="module")
def spark():
    pytest.importorskip("pyspark")
    from pyspark.sql import SparkSession
    s = SparkSession.builder.master("local[2]").appName("r14-test").getOrCreate()
    yield s
    s.stop()


def test_spark_cleaning_matches_pandas_rules(spark):
    from spark.sales_backfill import clean_sales
    rows = [("2024-01-01", "SKU1", "W1", "2", "10.5"),
            ("2024-01-01", "SKU1", "W1", "2", "10.5"),
            ("2024-01-02", "SKU2", "W1", "3", "4.0")]
    got = clean_sales(spark.createDataFrame(rows, COLS)).orderBy("date", "sku_id").toPandas()
    exp = pd.DataFrame(rows, columns=COLS).drop_duplicates().copy()
    exp["date"] = pd.to_datetime(exp["date"]).dt.date
    exp["quantity_sold"] = exp["quantity_sold"].astype(int)
    exp["unit_price"] = exp["unit_price"].astype(float)
    pd.testing.assert_frame_equal(got.reset_index(drop=True), exp.reset_index(drop=True), check_dtype=False)


def test_uncastable_rows_are_rejected_not_loaded(spark):
    from spark.sales_backfill import clean_sales
    rows = [("2024-01-01", "SKU1", "W1", None, "1.0"),
            ("2024-01-01", "SKU2", "W1", "abc", "1.0"),
            ("not-a-date", "SKU3", "W1", "1", "1.0"),
            ("2024-01-01", "SKU4", "W1", "1", "1.0")]
    got = clean_sales(spark.createDataFrame(rows, COLS)).collect()
    assert [r["sku_id"] for r in got] == ["SKU4"]


def test_same_key_last_row_wins(spark):
    from spark.sales_backfill import _prepare, dedupe_by_key
    rows = [("2024-01-01", "SKU1", "W1", "1", "1.0"),
            ("2024-01-01", "SKU1", "W1", "9", "2.0"),
            ("2024-01-01", "SKU1", "W1", "1", "1.0")]  # exact dup of row 1 must not win
    out = dedupe_by_key(_prepare(spark.createDataFrame(rows, COLS))).collect()
    assert len(out) == 1 and out[0]["quantity_sold"] == 9


# ---------- integration: real Postgres (docker compose up postgres; set DB_*) ----------
@pytest.mark.integration
def test_month_rerun_is_idempotent_and_isolated(tmp_path, monkeypatch):
    psycopg2 = pytest.importorskip("psycopg2")
    pytest.importorskip("pyspark")
    if not os.getenv("DB_PASSWORD"):
        pytest.skip("DB_PASSWORD not set")
    monkeypatch.setenv("DB_HOST", os.getenv("DB_HOST", "localhost"))
    from spark.sales_backfill import db_config, run

    csv = tmp_path / "h.csv"
    csv.write_text("\n".join([
        ",".join(COLS),
        "2024-01-05,R14T1,W1,3,10.0",
        "2024-01-05,R14T1,W1,3,10.0",     # exact duplicate
        "2024-01-06,R14T2,W1,1,5.0",
        "2024-01-06,R14T2,W1,9,6.0",      # key collision: last wins
        "2024-02-05,R14T3,W1,2,7.5",
        "2024-02-06,R14T4,W1,,3.0",       # rejected
    ]) + "\n")

    def q(sql, args=()):
        c = psycopg2.connect(**db_config())
        try:
            with c, c.cursor() as cur:
                cur.execute(sql, args or None)
                return cur.fetchall() if cur.description else None
        finally:
            c.close()

    q("DELETE FROM sales_fact WHERE sku_id LIKE 'R14T%'")
    try:
        first = run(str(csv), "2024-01", "2024-02")
        assert first["rejected_rows_total"] == 1
        snap = q("SELECT date, sku_id, quantity_sold, unit_price FROM sales_fact "
                 "WHERE sku_id LIKE 'R14T%' ORDER BY date, sku_id")
        assert len(snap) == 3
        assert [float(r[3]) for r in snap if r[1] == "R14T2"] == [6.0]
        assert [r[2] for r in snap if r[1] == "R14T2"] == [9]

        jan_before = q("SELECT sku_id, updated_at FROM sales_fact WHERE sku_id IN ('R14T1','R14T2') ORDER BY sku_id")
        run(str(csv), "2024-02", "2024-02")          # re-run ONE month
        jan_after = q("SELECT sku_id, updated_at FROM sales_fact WHERE sku_id IN ('R14T1','R14T2') ORDER BY sku_id")
        assert jan_before == jan_after                # other month untouched

        run(str(csv), "2024-01", "2024-02")          # full re-run
        assert q("SELECT date, sku_id, quantity_sold, unit_price FROM sales_fact "
                 "WHERE sku_id LIKE 'R14T%' ORDER BY date, sku_id") == snap  # no dup rows, same data
    finally:
        q("DELETE FROM sales_fact WHERE sku_id LIKE 'R14T%'")
