import time
import tracemalloc
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from src.postgres_profiler import PostgresPushdownProfiler
from src.profile import profile

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
    engine = create_engine(DB_URL)
    df = seed_database(engine)

    print("\n--- Running In-Memory Pandas Profiler ---")
    pandas_report, pandas_time, pandas_mem = measure_execution(profile, df)
    print(f"Pandas Profile Time : {pandas_time:.2f}s")
    print(f"Pandas Peak Memory  : {pandas_mem:.2f} MB")

    print("\n--- Running SQL Pushdown Profiler ---")
    pushdown = PostgresPushdownProfiler(engine)
    sql_report, sql_time, sql_mem = measure_execution(pushdown.profile_table, TABLE_NAME)
    print(f"SQL Pushdown Time   : {sql_time:.2f}s")
    print(f"SQL Peak Memory     : {sql_mem:.2f} MB")

    print("\n========== METRIC PARITY CHECK ==========")
    p_stat = pandas_report["statistics"]["quantity_sold"]
    s_stat = sql_report["statistics"]["quantity_sold"]

    print(f"Count  -> Pandas: {p_stat['count']} | SQL: {s_stat['count']}")
    print(f"Mean   -> Pandas: {p_stat['mean']:.4f} | SQL: {s_stat['mean']:.4f}")
    print(f"Median -> Pandas: {p_stat['50%']:.4f} | SQL: {s_stat['50%']:.4f}")
    print(f"Max    -> Pandas: {p_stat['max']} | SQL: {s_stat['max']}")

    # Save benchmark results
    out_dir = Path("reports")
    out_dir.mkdir(exist_ok=True)
    summary_df = pd.DataFrame([
        {
            "mode": "pandas_in_memory",
            "rows": ROW_COUNT,
            "time_seconds": round(pandas_time, 2),
            "peak_memory_mb": round(pandas_mem, 2),
        },
        {
            "mode": "sql_pushdown",
            "rows": ROW_COUNT,
            "time_seconds": round(sql_time, 2),
            "peak_memory_mb": round(sql_mem, 2),
        },
    ])
    summary_df.to_csv(out_dir / "pushdown_benchmark_results.csv", index=False)
    print(f"\nBenchmark summary written to reports/pushdown_benchmark_results.csv")


if __name__ == "__main__":
    main()