"""
R5 #5: Find the real performance ceiling.

Pushes bulk_upsert() row counts up (50k, 100k, 200k, 500k, 1M by default)
against a disposable scratch table and reports actual wall-clock time for
each, stopping early if a run either raises an exception or exceeds
MAX_ACCEPTABLE_SECONDS. Prints an honest ceiling based on what actually
happened on this machine/DB - not a guess.

IMPORTANT: run this for real against your Docker Postgres and paste the
printed table into the README's performance section. Numbers vary a lot by
machine/disk/DB config, so this script's own output is the only trustworthy
source of them - do not carry over numbers from a different environment.

Usage:
    cd etl/src && python3 ../../scripts/performance_ceiling_check.py
"""

import gc
import os
import random
import sys
import time
import tracemalloc
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "etl" / "src"))
os.chdir(REPO_ROOT)

from sqlalchemy import text

from database import get_engine
from load import bulk_upsert


TABLE = "sales_fact_perf_ceiling_check"
ROW_COUNTS = [50_000, 100_000, 200_000, 500_000, 1_000_000]
MAX_ACCEPTABLE_SECONDS = 120  # beyond this, "works" stops meaning "acceptable"
CHUNK_SIZE = 5000


def setup_scratch_table(engine):
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TABLE};"))
        conn.execute(text(f"""
            CREATE TABLE {TABLE} (
                id BIGSERIAL PRIMARY KEY,
                date DATE NOT NULL,
                sku_id VARCHAR(50) NOT NULL,
                warehouse_id VARCHAR(20) NOT NULL,
                quantity_sold INTEGER,
                unit_price NUMERIC(12,2),
                source_batch VARCHAR(100),
                run_id BIGINT,
                pipeline_version VARCHAR(20),
                loaded_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(date, sku_id, warehouse_id)
            );
        """))


def teardown_scratch_table(engine):
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TABLE};"))


def generate_rows(n, seed=42):
    random.seed(seed)
    skus = [f"SKU{i}" for i in range(20_000)]
    warehouses = [f"WH{i}" for i in range(1, 21)]
    start_date = date(2015, 1, 1)

    rows = []
    for i in range(n):
        rows.append({
            "date": start_date + timedelta(days=i % 3650),
            "sku_id": skus[i % len(skus)],
            "warehouse_id": warehouses[i % len(warehouses)],
            "quantity_sold": random.randint(1, 500),
            "unit_price": round(random.uniform(1, 999), 2),
            "source_batch": "perf_ceiling_check.csv",
            "run_id": 0,
            "pipeline_version": "1.0.0",
        })
    return rows


def main():
    engine = get_engine()

    columns = [
        "date", "sku_id", "warehouse_id", "quantity_sold", "unit_price",
        "source_batch", "run_id", "pipeline_version",
    ]

    results = []

    for n in ROW_COUNTS:
        print(f"\n{'=' * 60}\nTesting {n:,} rows\n{'=' * 60}")

        try:
            print(f"Generating {n:,} synthetic rows...")
            gen_start = time.perf_counter()
            records = generate_rows(n)
            gen_elapsed = time.perf_counter() - gen_start
            print(f"  generation: {gen_elapsed:.2f}s")

            setup_scratch_table(engine)

            tracemalloc.start()
            start = time.perf_counter()

            bulk_upsert(
                engine=engine,
                table_name=TABLE,
                columns=columns,
                conflict_keys=["date", "sku_id", "warehouse_id"],
                records=records,
                chunk_size=CHUNK_SIZE,
            )

            elapsed = time.perf_counter() - start
            _, peak_mem = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            teardown_scratch_table(engine)
            del records
            gc.collect()

            rows_per_sec = n / elapsed if elapsed > 0 else float("inf")
            peak_mem_mb = peak_mem / (1024 * 1024)

            print(f"  load time    : {elapsed:.2f}s")
            print(f"  throughput   : {rows_per_sec:,.0f} rows/sec")
            print(f"  peak memory  : {peak_mem_mb:.1f} MB (Python-side, tracemalloc)")

            results.append({
                "rows": n, "elapsed": elapsed, "rows_per_sec": rows_per_sec,
                "peak_mem_mb": peak_mem_mb,
                "status": ("SLOW / CEILING" if elapsed > MAX_ACCEPTABLE_SECONDS else "OK"),
            })

            if elapsed > MAX_ACCEPTABLE_SECONDS:
                print(f"\n  >>> Exceeded MAX_ACCEPTABLE_SECONDS ({MAX_ACCEPTABLE_SECONDS}s). "
                      f"Stopping: this is the operational loader ceiling for this run.")
                break

        except Exception as e:
            print(f"\n  >>> FAILED at {n:,} rows: {type(e).__name__}: {e}")
            results.append({
                "rows": n, "elapsed": None, "rows_per_sec": None,
                "peak_mem_mb": None, "status": f"FAILED: {e}",
            })
            try:
                teardown_scratch_table(engine)
            except Exception:
                pass
            break

    print(f"\n\n{'=' * 70}")
    print("PERFORMANCE CEILING - HONEST RESULTS (paste this into the README)")
    print("=" * 70)
    print(f"{'Rows':>12} | {'Time (s)':>10} | {'Rows/sec':>12} | {'Peak MB':>9} | Status")
    print("-" * 70)
    for r in results:
        elapsed_str = f"{r['elapsed']:.2f}" if r["elapsed"] is not None else "-"
        rps_str = f"{r['rows_per_sec']:,.0f}" if r["rows_per_sec"] is not None else "-"
        mem_str = f"{r['peak_mem_mb']:.1f}" if r["peak_mem_mb"] is not None else "-"
        print(f"{r['rows']:>12,} | {elapsed_str:>10} | {rps_str:>12} | {mem_str:>9} | {r['status']}")
    print("=" * 70)

    acceptable = [r for r in results if r["status"] == "OK"]
    if acceptable:
        ceiling = acceptable[-1]
        print(f"\nLargest tested size within {MAX_ACCEPTABLE_SECONDS}s: {ceiling['rows']:,} rows "
              f"in {ceiling['elapsed']:.1f}s ({ceiling['rows_per_sec']:,.0f} rows/sec).")
    boundary = [r for r in results if r["status"] == "SLOW / CEILING"]
    if boundary:
        print(f"Operational boundary: {boundary[0]['rows']:,} rows - {boundary[0]['elapsed']:.1f}s; "
              "the benchmark stops here because the configured runtime threshold was exceeded.")
    print("\nInvestigation note: this benchmark isolates bulk_upsert() and excludes sales history-copy overhead; "
          "therefore the observed boundary is an application/loader benchmark result, not a PostgreSQL theoretical limit.")


if __name__ == "__main__":
    main()
