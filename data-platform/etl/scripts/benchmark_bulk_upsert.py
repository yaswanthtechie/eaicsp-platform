"""
R4 #3: Bulk upsert performance benchmark.

Generates a 100,000-row synthetic batch, times the existing row-by-row
upsert pattern (one INSERT round-trip per row, same as load.py's
load_data()) against the new bulk_upsert() (one multi-row
INSERT...ON CONFLICT statement per chunk), and prints both timings plus the
speedup factor.

Runs entirely against a disposable scratch table (sales_fact_benchmark) so
it never touches real sales_fact/sales_fact_history data. Safe to run
repeatedly - the scratch table is dropped and recreated each run.

Usage:
    cd etl/src && python3 ../../scripts/benchmark_bulk_upsert.py
"""

import os
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "etl" / "src"))
os.chdir(REPO_ROOT)

from sqlalchemy import text
from database import get_engine
from load import bulk_upsert


N_ROWS = 100_000
CHUNK_SIZE = 5_000


def generate_rows(n, run_id, seed=42):
    random.seed(seed)

    skus = [f"SKU{i}" for i in range(2000)]
    warehouses = [f"WH{i}" for i in range(1, 11)]
    start_date = date(2020, 1, 1)

    rows = []
    for i in range(n):
        rows.append({
            "date": start_date + timedelta(days=i % 1000),
            "sku_id": skus[i % len(skus)],
            "warehouse_id": warehouses[i % len(warehouses)],
            "quantity_sold": random.randint(1, 500),
            "unit_price": round(random.uniform(1, 999), 2),
            "source_batch": "benchmark.csv",
            "run_id": run_id,
            "pipeline_version": "1.0.0",
        })
    return rows


def setup_scratch_table(engine):
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS sales_fact_benchmark;"))
        conn.execute(text("""
            CREATE TABLE sales_fact_benchmark (
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
        conn.execute(text("DROP TABLE IF EXISTS sales_fact_benchmark;"))


def row_by_row_upsert(engine, records):
    """Same pattern as load.py's load_data(): one INSERT...ON CONFLICT
    round-trip per row (history-copy omitted here for a fair apples-to-apples
    comparison against bulk_upsert(), which is also benchmarked without its
    optional history step)."""

    upsert_query = text("""
        INSERT INTO sales_fact_benchmark (
            date, sku_id, warehouse_id, quantity_sold, unit_price,
            source_batch, run_id, pipeline_version
        )
        VALUES (
            :date, :sku_id, :warehouse_id, :quantity_sold, :unit_price,
            :source_batch, :run_id, :pipeline_version
        )
        ON CONFLICT (date, sku_id, warehouse_id)
        DO UPDATE SET
            quantity_sold = EXCLUDED.quantity_sold,
            unit_price = EXCLUDED.unit_price,
            source_batch = EXCLUDED.source_batch,
            run_id = EXCLUDED.run_id,
            pipeline_version = EXCLUDED.pipeline_version,
            updated_at = NOW();
    """)

    with engine.begin() as connection:
        for record in records:
            connection.execute(upsert_query, record)


def main():
    engine = get_engine()

    print(f"Generating {N_ROWS:,} synthetic rows...")
    records = generate_rows(N_ROWS, run_id=0)

    columns = [
        "date", "sku_id", "warehouse_id", "quantity_sold", "unit_price",
        "source_batch", "run_id", "pipeline_version",
    ]
    conflict_keys = ["date", "sku_id", "warehouse_id"]

    # --- Row-by-row (current/legacy pattern) ---
    setup_scratch_table(engine)
    print(f"\nRunning ROW-BY-ROW upsert on {N_ROWS:,} rows...")
    start = time.perf_counter()
    row_by_row_upsert(engine, records)
    row_by_row_elapsed = time.perf_counter() - start
    print(f"Row-by-row upsert: {row_by_row_elapsed:.2f} sec")

    # --- Bulk (R4 implementation) ---
    setup_scratch_table(engine)
    print(f"\nRunning BULK upsert on {N_ROWS:,} rows (chunk_size={CHUNK_SIZE})...")
    start = time.perf_counter()
    bulk_upsert(
        engine=engine,
        table_name="sales_fact_benchmark",
        columns=columns,
        conflict_keys=conflict_keys,
        records=records,
        history_copy_fn=None,
        chunk_size=CHUNK_SIZE,
    )
    bulk_elapsed = time.perf_counter() - start
    print(f"Bulk upsert: {bulk_elapsed:.2f} sec")

    teardown_scratch_table(engine)

    speedup = row_by_row_elapsed / bulk_elapsed if bulk_elapsed > 0 else float("inf")

    print("\n" + "=" * 50)
    print("BULK UPSERT BENCHMARK RESULTS")
    print("=" * 50)
    print(f"Rows:            {N_ROWS:,}")
    print(f"Row-by-row time: {row_by_row_elapsed:.2f} sec")
    print(f"Bulk time:       {bulk_elapsed:.2f} sec")
    print(f"Speedup:         {speedup:.1f}x")
    print("=" * 50)


if __name__ == "__main__":
    main()
