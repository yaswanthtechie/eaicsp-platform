"""Postgres vs ClickHouse date-range aggregation benchmark (R12-13 M2).
    python scripts/benchmark_postgres_clickhouse.py --rows 1200000
Generates N rows in Postgres (deterministic), copies them to ClickHouse, then
times the SAME aggregation on both engines. For each query: 1 warm-up run
(discarded) + ``--runs`` timed runs; reports min and median wall-clock seconds,
measured client-side (includes network + result transfer).
Fairness choices (so the numbers are not rigged either way):
  * Postgres gets a btree index on (sale_date, warehouse_id) and ANALYZE.
  * Two queries: a full-year range (touches 100% of rows: index cannot help)
    and a one-quarter range (~25% of rows).
  * Result sets are compared for equality; a mismatch is reported, not hidden.
Writes docs/r12_13_clickhouse_benchmark.json including the environment.
"""
from __future__ import annotations
import argparse
import json
import os
import platform
import statistics
import time
from pathlib import Path
QUERIES = {
    "full_year_2024": ("2024-01-01", "2024-12-31"),
    "one_quarter_q2_2024": ("2024-04-01", "2024-06-30"),
}
SQL = """
SELECT warehouse_id, SUM(quantity_sold) AS units_sold,
       SUM(quantity_sold * unit_price) AS sales_amount
FROM benchmark_sales
WHERE sale_date BETWEEN '{lo}' AND '{hi}'
GROUP BY warehouse_id
ORDER BY warehouse_id
"""
def pg_conn():
    import psycopg2
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "postgres"), port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "salesdb"), user=os.getenv("DB_USER", "admin"),
        password=os.getenv("DB_PASSWORD", ""),
    )
def timed(fn, runs):
    fn()  # warm-up, discarded
    samples = []
    result = None
    for _ in range(runs):
        t = time.perf_counter()
        result = fn()
        samples.append(time.perf_counter() - t)
    return result, samples
def summarise(samples):
    return {"min_s": round(min(samples), 4), "median_s": round(statistics.median(samples), 4), "max_s": round(max(samples), 4), "spread_s": round(max(samples) - min(samples), 4), "runs": len(samples)}
def normalise(rows):
    return [(r[0], int(r[1]), round(float(r[2]), 2)) for r in rows]
def main(rows, runs, skip_clickhouse):
    pg = pg_conn()
    pg.autocommit = False
    with pg.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS benchmark_sales")
        cur.execute("""CREATE TABLE benchmark_sales (
            sale_date DATE NOT NULL, warehouse_id TEXT NOT NULL,
            quantity_sold INTEGER NOT NULL, unit_price NUMERIC(12,2) NOT NULL)""")
        t = time.perf_counter()
        cur.execute("""
            INSERT INTO benchmark_sales
            SELECT make_date(2024, (i %% 12) + 1, (i %% 28) + 1),
                   'WH-' || lpad((i %% 100)::text, 3, '0'),
                   (i %% 20) + 1,
                   ((i %% 5000) + 100) / 100.0
            FROM generate_series(0, %s - 1) AS i""", (rows,))
        gen_s = time.perf_counter() - t
        cur.execute("CREATE INDEX ON benchmark_sales (sale_date, warehouse_id)")
        cur.execute("ANALYZE benchmark_sales")
        cur.execute("SELECT count(*) FROM benchmark_sales")
        assert cur.fetchone()[0] == rows
    report = {
        "rows": rows, "runs_per_query": runs, "generation_seconds": round(gen_s, 2),
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "cpu_count": os.cpu_count()},
        "note": "Wall-clock, client-side, warm cache, single node, default configs.",
        "queries": {},
    }
    ch = None
    if not skip_clickhouse:
        import clickhouse_connect
        ch = clickhouse_connect.get_client(
            host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
            port=int(os.getenv("CLICKHOUSE_PORT", 8123)),
            username=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", ""), send_receive_timeout=300)
        ch.command("DROP TABLE IF EXISTS benchmark_sales")
        ch.command("""CREATE TABLE benchmark_sales (
            sale_date Date, warehouse_id String, quantity_sold Int32,
            unit_price Decimal(12,2)) ENGINE=MergeTree ORDER BY (sale_date, warehouse_id)""")
        pg.commit()
        with pg.cursor(name="copy_cursor") as cur:  # server-side cursor, bounded memory
            cur.execute("SELECT sale_date, warehouse_id, quantity_sold, unit_price::double precision FROM benchmark_sales")
            while True:
                batch = cur.fetchmany(100_000)
                if not batch:
                    break
                ch.insert("benchmark_sales", batch,
                          column_names=["sale_date", "warehouse_id", "quantity_sold", "unit_price"])
        assert ch.query("SELECT count() FROM benchmark_sales").result_rows[0][0] == rows
    for name, (lo, hi) in QUERIES.items():
        sql = SQL.format(lo=lo, hi=hi)
        def run_pg():
            with pg.cursor() as cur:
                cur.execute(sql)
                return cur.fetchall()
        pg_rows, pg_samples = timed(run_pg, runs)
        entry = {"postgres": summarise(pg_samples)}
        if ch is not None:
            ch_rows, ch_samples = timed(lambda: ch.query(sql).result_rows, runs)
            entry["clickhouse"] = summarise(ch_samples)
            entry["results_match"] = normalise(pg_rows) == normalise(ch_rows)
            entry["speedup_median_x"] = round(
                entry["postgres"]["median_s"] / max(entry["clickhouse"]["median_s"], 1e-9), 1)
        report["queries"][name] = entry
    pg.close()
    if ch is not None:
        ch.close()
    out = Path("docs/r12_13_clickhouse_benchmark.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=1_200_000)
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--skip-clickhouse", action="store_true",
                    help="time Postgres only (e.g. no ClickHouse available)")
    a = ap.parse_args()
    if a.rows < 1_000_000:
        raise SystemExit("R12-13 benchmark requires at least 1,000,000 rows")
    main(a.rows, a.runs, a.skip_clickhouse)

