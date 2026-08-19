"""
R4 #5: Backfill idempotency stress test.

Runs the R3 run_backfill() twice over overlapping date ranges and proves,
with actual row counts queried from the database, that the second run does
not change sales_fact's row count or duplicate any rows.

Usage:
    cd etl/src && python3 ../../scripts/test_backfill_idempotency.py
"""

import os
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "etl" / "src"))
os.chdir(REPO_ROOT)  # extract_data() resolves source_path relative to cwd

from sqlalchemy import text
from database import get_engine
from pipeline import run_backfill


def row_count(engine, table="sales_fact"):
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


def main():
    engine = get_engine()

    from_date = date(2024, 1, 1)
    to_date = date(2024, 1, 6)
    overlap_from = date(2024, 1, 3)  # overlaps the first range
    overlap_to = date(2024, 1, 6)

    print(f"Backfill run 1: {from_date} to {to_date}")
    run_backfill(from_date, to_date)
    count_after_run1 = row_count(engine)
    print(f"sales_fact row count after run 1: {count_after_run1}")

    print(f"\nBackfill run 2 (overlapping range): {overlap_from} to {overlap_to}")
    run_backfill(overlap_from, overlap_to)
    count_after_run2 = row_count(engine)
    print(f"sales_fact row count after run 2: {count_after_run2}")

    print(f"\nBackfill run 3 (same overlapping range again): {overlap_from} to {overlap_to}")
    run_backfill(overlap_from, overlap_to)
    count_after_run3 = row_count(engine)
    print(f"sales_fact row count after run 3: {count_after_run3}")

    print("\n" + "=" * 50)
    print("BACKFILL IDEMPOTENCY RESULTS")
    print("=" * 50)
    print(f"After run 1: {count_after_run1} rows")
    print(f"After run 2: {count_after_run2} rows")
    print(f"After run 3: {count_after_run3} rows")

    if count_after_run1 == count_after_run2 == count_after_run3:
        print("PASS: row count unchanged across overlapping re-runs.")
    else:
        print("FAIL: row count changed - backfill is not idempotent!")
        sys.exit(1)
    print("=" * 50)


if __name__ == "__main__":
    main()
