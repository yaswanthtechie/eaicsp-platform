"""
R5 #3: Point-in-time reconstruction proof against a real database.

Loads a row for SKU888/WH1 in "run A" (quantity_sold=100), then loads a
correction for the SAME row in "run B" (quantity_sold=200, which triggers
_bulk_copy_sales_history to preserve the run-A value). Then calls
sales_fact_as_of_run(run_A_id) and shows it correctly returns the OLD value
(100) - proving we can answer "what did sales_fact look like right after
run A?" even though the table has since moved on to 200.

Runs against real sales_fact/sales_fact_history rows, all tagged with a
dedicated SKU so they're easy to find and clean up.

Usage:
    cd etl/src && python3 ../../scripts/point_in_time_check.py
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "etl" / "src"))
os.chdir(REPO_ROOT)

from sqlalchemy import text

from database import get_engine
from logger import create_run, finish_run
from load import bulk_upsert, _bulk_copy_sales_history
from reconstruct import sales_fact_as_of_run


SKU = "SKU888_PIT_CHECK"
COLUMNS = [
    "date", "sku_id", "warehouse_id", "quantity_sold", "unit_price",
    "source_batch", "run_id", "pipeline_version",
]


def cleanup(engine):
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM sales_fact_history WHERE sku_id = :sku"),
            {"sku": SKU},
        )
        conn.execute(
            text("DELETE FROM sales_fact WHERE sku_id = :sku"),
            {"sku": SKU},
        )


def load_one(engine, run_id, quantity_sold):
    record = {
        "date": "2024-09-01", "sku_id": SKU, "warehouse_id": "WH1",
        "quantity_sold": quantity_sold, "unit_price": 9.99,
        "source_batch": f"pit_check_run_{run_id}.csv",
        "run_id": run_id, "pipeline_version": "1.0.0",
    }
    bulk_upsert(
        engine=engine,
        table_name="sales_fact",
        columns=COLUMNS,
        conflict_keys=["date", "sku_id", "warehouse_id"],
        records=[record],
        history_copy_fn=_bulk_copy_sales_history,
    )
    from datetime import datetime
    finish_run(
        run_id=run_id, end_time=datetime.now(), status="SUCCESS",
        batches_seen=1, rows_inserted=1, rows_updated=0, rows_rejected=0,
    )


def main():
    engine = get_engine()
    cleanup(engine)

    print(f"Run A: loading {SKU} with quantity_sold=100...")
    run_a_id = create_run()
    load_one(engine, run_a_id, quantity_sold=100)

    print(f"Run B: correcting {SKU} to quantity_sold=200...")
    run_b_id = create_run()
    load_one(engine, run_b_id, quantity_sold=200)

    with engine.connect() as conn:
        current = conn.execute(
            text("SELECT quantity_sold FROM sales_fact WHERE sku_id = :sku"),
            {"sku": SKU},
        ).fetchone()

    print(f"\nCurrent sales_fact value right now: quantity_sold={current.quantity_sold}")

    print(f"\nReconstructing sales_fact as of run A (run_id={run_a_id})...")
    as_of_a = sales_fact_as_of_run(run_a_id, engine=engine)
    row_a = next((r for r in as_of_a if r["sku_id"] == SKU), None)

    print(f"Reconstructed value at run A: {row_a['quantity_sold'] if row_a else 'NOT FOUND'}")

    print("=" * 60)
    print("POINT-IN-TIME RECONSTRUCTION CHECK")
    print("=" * 60)
    print(f"Current (live) value       : {current.quantity_sold}")
    print(f"Reconstructed as-of-run-A  : {row_a['quantity_sold'] if row_a else None}")
    print(f"Expected as-of-run-A       : 100")

    cleanup(engine)

    if row_a is not None and row_a["quantity_sold"] == 100:
        print("\nPASS: reconstructed the pre-correction state correctly using")
        print("      loaded_at/updated_at + sales_fact_history, read-only.")
    else:
        print("\nFAIL: reconstruction did not return the expected historical value.")
        sys.exit(1)


if __name__ == "__main__":
    main()
