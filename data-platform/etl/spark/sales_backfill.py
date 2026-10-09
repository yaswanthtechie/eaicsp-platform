"""PySpark historical sales backfill (Round 14).

Cleaning mirrors etl.src.transform.transform_data plus the loader's key rule:
  1. exact duplicate rows removed (keep first occurrence, like pandas drop_duplicates)
  2. date -> DATE, quantity_sold -> INT, unit_price -> DOUBLE
  3. rows that fail the cast (NULL after cast) are rejected and counted
     (pandas would raise / the quality gate would quarantine them)
  4. same (date, sku_id, warehouse_id) key with different values: LAST row in
     input order wins (same as load._dedupe_records without a priority key)

Each month is upserted and then verified against Postgres independently, so a
failed month can be re-run alone. A month is NOT one DB transaction (each Spark
partition commits itself); safety comes from the idempotent upsert + verification.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date

COLUMNS = ["date", "sku_id", "warehouse_id", "quantity_sold", "unit_price"]
KEY = ["date", "sku_id", "warehouse_id"]
PIPELINE_VERSION = "r14-spark-1.1"
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


# ---------- pure helpers (no Spark needed) ----------
def validate_month(value: str) -> str:
    if not isinstance(value, str) or not MONTH_RE.match(value):
        raise ValueError(f"invalid month {value!r}; expected YYYY-MM")
    return value


def month_bounds(month: str):
    validate_month(month)
    year, mon = (int(x) for x in month.split("-"))
    start = date(year, mon, 1)
    end = date(year + (mon == 12), 1 if mon == 12 else mon + 1, 1)
    return start.isoformat(), end.isoformat()


def month_list(start_month: str, end_month: str):
    validate_month(start_month)
    validate_month(end_month)
    if start_month > end_month:
        raise ValueError(f"start_month {start_month} is after end_month {end_month}")
    sy, sm = map(int, start_month.split("-"))
    ey, em = map(int, end_month.split("-"))
    cur, end = sy * 12 + sm - 1, ey * 12 + em - 1
    while cur <= end:
        yield f"{cur // 12:04d}-{cur % 12 + 1:02d}"
        cur += 1


def db_config():
    return {
        "host": os.getenv("DB_HOST", "postgres"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "salesdb"),
        "user": os.getenv("DB_USER", "admin"),
        "password": os.environ["DB_PASSWORD"],
    }


# ---------- Spark cleaning ----------
def _with_order(df):
    from pyspark.sql import functions as F
    return df if "_ord" in df.columns else df.withColumn("_ord", F.monotonically_increasing_id())


def cast_sales(df):
    from pyspark.sql import functions as F
    return (
        df.withColumn("date", F.to_date("date"))
        .withColumn("quantity_sold", F.col("quantity_sold").cast("int"))
        .withColumn("unit_price", F.col("unit_price").cast("double"))
    )


def valid_condition():
    from pyspark.sql import functions as F
    cond = F.lit(True)
    for c in COLUMNS:
        cond = cond & F.col(c).isNotNull()
    return cond


def _prepare(df):
    """cast -> drop rejected -> exact-dedupe keeping first input row. Keeps _ord."""
    from pyspark.sql import functions as F
    casted = cast_sales(_with_order(df))
    return (
        casted.filter(valid_condition())
        .groupBy(*COLUMNS)
        .agg(F.min("_ord").alias("_ord"))
    )


def clean_sales(df):
    """Public: same rules as the pandas transform (+ reject uncastable rows)."""
    return _prepare(df).select(*COLUMNS)


def dedupe_by_key(df):
    """Same key, different values: last input row wins. Needs _ord."""
    from pyspark.sql import Window, functions as F
    w = Window.partitionBy(*KEY).orderBy(F.col("_ord").desc())
    return (
        df.withColumn("_rn", F.row_number().over(w))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )


# ---------- Postgres ----------
def _upsert_partition(rows, config):
    import psycopg2
    from psycopg2.extras import execute_batch
    sql = """
        INSERT INTO sales_fact
            (date, sku_id, warehouse_id, quantity_sold, unit_price,
             source_batch, run_id, pipeline_version)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (date, sku_id, warehouse_id)
        DO UPDATE SET
            quantity_sold = EXCLUDED.quantity_sold,
            unit_price = EXCLUDED.unit_price,
            source_batch = EXCLUDED.source_batch,
            run_id = EXCLUDED.run_id,
            pipeline_version = EXCLUDED.pipeline_version,
            updated_at = NOW()
    """
    conn = psycopg2.connect(**config)
    try:
        with conn:
            with conn.cursor() as cur:
                batch = []
                for r in rows:
                    batch.append((r["date"], r["sku_id"], r["warehouse_id"],
                                  r["quantity_sold"], r["unit_price"],
                                  r["source_batch"], r["run_id"], r["pipeline_version"]))
                    if len(batch) >= 5000:
                        execute_batch(cur, sql, batch, page_size=1000)
                        batch.clear()
                if batch:
                    execute_batch(cur, sql, batch, page_size=1000)
    finally:
        conn.close()


def verify_month(month: str, expected: dict):
    """Compare what Spark meant to write with what Postgres holds for this month."""
    import psycopg2
    start, end = month_bounds(month)
    conn = psycopg2.connect(**db_config())
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*), COALESCE(SUM(quantity_sold),0), COALESCE(SUM(unit_price),0) "
                "FROM sales_fact WHERE date >= %s AND date < %s AND source_batch = %s",
                (start, end, f"spark_backfill_{month}"),
            )
            cnt, qty, price = cur.fetchone()
    finally:
        conn.close()
    got = {"rows": int(cnt), "qty": int(qty), "price": float(price)}
    ok = (got["rows"] == expected["rows"] and got["qty"] == expected["qty"]
          and abs(got["price"] - expected["price"]) <= 0.01)
    return ok, got


def upsert_month(prepared, month: str, run_id: str):
    from pyspark import StorageLevel
    from pyspark.sql import functions as F
    start, end = month_bounds(month)
    monthly = dedupe_by_key(
        prepared.filter((F.col("date") >= F.lit(start).cast("date"))
                        & (F.col("date") < F.lit(end).cast("date")))
    ).drop("_ord")
    monthly = (
        monthly.withColumn("source_batch", F.lit(f"spark_backfill_{month}"))
        .withColumn("run_id", F.lit(int(run_id)).cast("bigint"))
        .withColumn("pipeline_version", F.lit(PIPELINE_VERSION))
        .persist(StorageLevel.MEMORY_AND_DISK)
    )
    try:
        agg = monthly.agg(F.count("*").alias("n"),
                          F.coalesce(F.sum("quantity_sold"), F.lit(0)).alias("q"),
                          F.coalesce(F.sum("unit_price"), F.lit(0.0)).alias("p")).collect()[0]
        expected = {"rows": int(agg["n"]), "qty": int(agg["q"]), "price": float(agg["p"])}
        cfg = db_config()
        monthly.foreachPartition(lambda rows: _upsert_partition(rows, cfg))
        ok, got = verify_month(month, expected)
        if not ok:
            raise RuntimeError(f"verification failed for {month}: spark={expected} postgres={got}")
        return {"month": month, "status": "ok", "rows": expected["rows"],
                "qty": expected["qty"], "price": round(expected["price"], 2), "verified": True}
    finally:
        monthly.unpersist()


# ---------- driver ----------
def run(input_path: str, start_month: str, end_month: str, run_id: str = "0"):
    from pyspark import StorageLevel
    from pyspark.sql import SparkSession, functions as F
    from pyspark.sql.types import StructType, StructField, StringType

    months = list(month_list(start_month, end_month))  # validate before starting Spark
    schema = StructType([StructField(c, StringType(), True) for c in COLUMNS])
    spark = (
        SparkSession.builder.appName("sales-historical-backfill-r14")
        .master(os.getenv("SPARK_MASTER", "local[*]"))
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", os.getenv("SPARK_SHUFFLE_PARTITIONS", "32"))
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )
    try:
        raw = spark.read.option("header", True).schema(schema).csv(input_path)
        base = _with_order(raw).persist(StorageLevel.MEMORY_AND_DISK)
        rejected = cast_sales(base).filter(~valid_condition()).count()
        prepared = _prepare(base).persist(StorageLevel.MEMORY_AND_DISK)
        results = []
        for month in months:
            try:
                results.append(upsert_month(prepared, month, run_id))
            except Exception as exc:  # isolate: one bad month must not stop the others
                results.append({"month": month, "status": "failed", "error": str(exc)[:500]})
        summary = {"rejected_rows_total": rejected, "months": results}
        print(json.dumps(summary, default=str))
        failed = [r["month"] for r in results if r["status"] != "ok"]
        if failed:
            raise RuntimeError(f"months failed (re-run only these): {failed}")
        return summary
    finally:
        spark.stop()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--start-month", required=True, type=validate_month, help="YYYY-MM")
    p.add_argument("--end-month", required=True, type=validate_month, help="YYYY-MM")
    p.add_argument("--run-id", default="0")
    a = p.parse_args()
    run(a.input, a.start_month, a.end_month, a.run_id)


if __name__ == "__main__":
    main()
