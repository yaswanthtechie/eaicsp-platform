"""Disposable before/after partitioning proof for date-range queries."""
import os, sys, time
from pathlib import Path
REPO_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO_ROOT/'etl'/'src')); os.chdir(REPO_ROOT)
from sqlalchemy import text
from database import get_engine


def timed(conn, sql):
    start=time.perf_counter(); conn.execute(text(sql)).scalar(); return time.perf_counter()-start


def main():
    engine=get_engine()
    with engine.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS sales_partition_bench CASCADE"))
        c.execute(text("DROP TABLE IF EXISTS sales_partitioned_bench CASCADE"))
        c.execute(text("CREATE TABLE sales_partition_bench AS SELECT * FROM sales_fact WITH NO DATA"))
        c.execute(text("INSERT INTO sales_partition_bench SELECT * FROM sales_fact"))
        c.execute(text("CREATE TABLE sales_partitioned_bench (LIKE sales_fact INCLUDING DEFAULTS) PARTITION BY RANGE (date)"))
        c.execute(text("CREATE TABLE sales_partitioned_bench_default PARTITION OF sales_partitioned_bench DEFAULT"))
        for m in range(1,13):
            start=f'2024-{m:02d}-01'; end=f'2025-01-01' if m==12 else f'2024-{m+1:02d}-01'
            c.execute(text(f"CREATE TABLE sales_partitioned_bench_{m:02d} PARTITION OF sales_partitioned_bench FOR VALUES FROM ('{start}') TO ('{end}')"))
        c.execute(text("INSERT INTO sales_partitioned_bench SELECT * FROM sales_fact"))
    with engine.connect() as c:
        before=timed(c,"SELECT COUNT(*) FROM sales_partition_bench WHERE date BETWEEN '2024-01-01' AND '2024-01-31'")
        after=timed(c,"SELECT COUNT(*) FROM sales_partitioned_bench WHERE date BETWEEN '2024-01-01' AND '2024-01-31'")
        plan=c.execute(text("EXPLAIN (FORMAT TEXT) SELECT COUNT(*) FROM sales_partitioned_bench WHERE date BETWEEN '2024-01-01' AND '2024-01-31'")).fetchall()
    with engine.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS sales_partition_bench CASCADE"))
        c.execute(text("DROP TABLE IF EXISTS sales_partitioned_bench CASCADE"))
    print(f"before (unpartitioned): {before:.6f}s")
    print(f"after  (partitioned):   {after:.6f}s")
    print(f"speedup: {before/after:.2f}x" if after else "speedup: n/a")
    print("partitioned query plan:")
    for row in plan: print(row[0])
    print("PASS: benchmark completed; inspect plan for partition pruning and use the timings as the environment-specific proof.")

if __name__=='__main__': main()
