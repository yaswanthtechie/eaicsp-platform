import json
import platform
import sys
import time
import tracemalloc
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from src.postgres_profiler import PostgresPushdownProfiler
from src.profile import profile
from src.db_config import get_db_url
from src.parity import compare_reports

RESULTS_DIR = Path(__file__).resolve().parent / "results"

def pandas_mode(engine, table_name):
    df = pd.read_sql_table(table_name, engine)     # the load is part of pandas mode
    return profile(df)

DB_URL = "postgresql+psycopg2://postgres:password@localhost:5433/profiling_db"
ROW_COUNT = 1_000_000
TABLE_NAME = "benchmark_1m_sales"


def seed_database(engine):
    print(f"Generating {ROW_COUNT:,} synthetic rows...")
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "sku_id": rng.choice([f"SKU{i:03d}" for i in range(1, 51)], size=ROW_COUNT),
        "warehouse_id": rng.choice(["WH1", "WH2", "WH3", "WH4", "WH5"], size=ROW_COUNT),
        "quantity_sold": rng.integers(1, 100, size=ROW_COUNT).astype(float),
        "unit_price": rng.uniform(10.0, 500.0, size=ROW_COUNT),
    })

    # Invalidate values to simulate real data
    null_idx = rng.choice(ROW_COUNT, size=int(ROW_COUNT * 0.03), replace=False)
    df.loc[null_idx, "quantity_sold"] = np.nan

    outlier_idx = rng.choice(ROW_COUNT, size=int(ROW_COUNT * 0.01), replace=False)
    df.loc[outlier_idx, "quantity_sold"] = 99999.0

    print("Uploading dataset to PostgreSQL...")
    start = time.perf_counter()
    df.to_sql(TABLE_NAME, engine, if_exists="replace", index=False, chunksize=50_000)
    print(f"Loaded to DB in {time.perf_counter() - start:.2f}s")
    return df


def measure_execution(func, *args, **kwargs):
    tracemalloc.start()
    start_time = time.perf_counter()

    result = func(*args, **kwargs)

    elapsed = time.perf_counter() - start_time
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = peak_memory / (1024 * 1024)
    return result, elapsed, peak_mb


def main():
    engine = create_engine(get_db_url())
    seed_database(engine)                          # don't keep the returned df around

    pandas_report, pandas_time, pandas_mem = measure_execution(pandas_mode, engine, TABLE_NAME)
    sql_report, sql_time, sql_mem = measure_execution(
        PostgresPushdownProfiler(engine).profile_table, TABLE_NAME)

    mismatches = compare_reports(pandas_report, sql_report)

    with engine.connect() as conn:
        pg_version = conn.execute(text("SELECT version()")).scalar()

    result = {
        "rows": ROW_COUNT,
        "pandas_in_memory": {"time_seconds": round(pandas_time, 2), "peak_python_mb": round(pandas_mem, 1)},
        "sql_pushdown": {"time_seconds": round(sql_time, 2), "peak_python_mb": round(sql_mem, 1)},
        "parity_mismatches": mismatches,
        "environment": {"python": sys.version.split()[0], "pandas": pd.__version__,
                        "postgres": pg_version, "machine": platform.processor()},
        "memory_note": "tracemalloc measures Python-heap allocations only.",
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "pushdown_benchmark.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))

    if mismatches:
        raise SystemExit(f"Parity FAILED: {len(mismatches)} mismatches")


if __name__ == "__main__":
    main()