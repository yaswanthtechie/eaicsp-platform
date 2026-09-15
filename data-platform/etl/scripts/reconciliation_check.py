"""
R5 #4: Automated reconciliation proof, including a deliberately-injected
mismatch (per the spec's definition of done).

Part 1 - happy path: loads a normal batch, reconciles, shows it matches.
Part 2 - injected failure: loads a batch, then manually DELETEs one row
straight out of the table afterwards (simulating a load-time silent partial
failure that no schema/quality check could ever catch, since those ran
before load and never look at the database again), reconciles again with
the SAME expected values, and shows reconcile_load() catches the mismatch
and writes a CRITICAL alert.

Runs against real sales_fact rows, all tagged with a dedicated SKU so
they're easy to find and clean up.

Usage:
    cd etl/src && python3 ../../scripts/reconciliation_check.py
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "etl" / "src"))
os.chdir(REPO_ROOT)

import pandas as pd
from sqlalchemy import text

from database import get_engine
from load import bulk_upsert
from reconciliation import reconcile_load


SKU_PREFIX = "SKU_RECON_CHECK"
COLUMNS = [
    "date", "sku_id", "warehouse_id", "quantity_sold", "unit_price",
    "source_batch", "run_id", "pipeline_version",
]

# Minimal stand-in for the SourceConfig dataclass - only the attributes
# reconcile_load() actually reads.
SOURCE_CONFIG = SimpleNamespace(
    name="sales",
    table="sales_fact",
    quality_check_column="quantity_sold",
    columns={
        "date": {}, "sku_id": {}, "warehouse_id": {},
        "quantity_sold": {}, "unit_price": {},
    },
)


def cleanup(engine):
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM etl_alerts WHERE message LIKE :pat"),
            {"pat": f"%{SKU_PREFIX}%"},
        )
        conn.execute(
            text("DELETE FROM sales_fact WHERE sku_id LIKE :pat"),
            {"pat": f"{SKU_PREFIX}%"},
        )


def make_batch(run_id, n_rows):
    rows = [
        {
            "date": "2024-10-01",
            "sku_id": f"{SKU_PREFIX}_{i}",
            "warehouse_id": "WH1",
            "quantity_sold": 10 + i,
            "unit_price": 5.00,
        }
        for i in range(n_rows)
    ]
    df = pd.DataFrame(rows)
    return [{"file_path": Path(f"recon_check_run_{run_id}.csv"), "data": df}]


def load_batch(engine, run_id, batches):
    records = []
    for batch in batches:
        for record in batch["data"].to_dict(orient="records"):
            record["source_batch"] = batch["file_path"].name
            record["run_id"] = run_id
            record["pipeline_version"] = "1.0.0"
            records.append(record)

    bulk_upsert(
        engine=engine,
        table_name="sales_fact",
        columns=COLUMNS,
        conflict_keys=["date", "sku_id", "warehouse_id"],
        records=records,
    )


def latest_alert(engine, run_id):
    with engine.connect() as conn:
        return conn.execute(
            text("""
                SELECT severity, message FROM etl_alerts
                WHERE run_id = :r ORDER BY created_at DESC LIMIT 1
            """),
            {"r": run_id},
        ).fetchone()


def main():
    engine = get_engine()
    cleanup(engine)

    # --- Part 1: happy path ---------------------------------------------
    print("Part 1: normal load, no injected failure")
    run_id_ok = 900001
    batches_ok = make_batch(run_id_ok, n_rows=5)
    load_batch(engine, run_id_ok, batches_ok)

    result_ok = reconcile_load(batches_ok, batches_ok, batches_ok, SOURCE_CONFIG, run_id_ok, engine=engine)
    print(f"  expected_rows={result_ok['raw_rows']} approved_rows={result_ok['approved_rows']} actual_rows={result_ok['actual_rows']} "
          f"matched={result_ok['matched']}")

    # --- Part 2: deliberately-injected mismatch -------------------------
    print("\nPart 2: same load, then a row is silently removed after load")
    print("(simulating a load-time failure schema/quality checks can't see)")
    run_id_bad = 900002
    batches_bad = make_batch(run_id_bad, n_rows=5)
    load_batch(engine, run_id_bad, batches_bad)

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM sales_fact WHERE sku_id = :sku AND run_id = :r"),
            {"sku": f"{SKU_PREFIX}_0", "r": run_id_bad},
        )

    # Reconcile with the SAME expected values as what was originally sent to
    # load - reconcile_load has no way of knowing a row vanished afterwards
    # except by actually checking the table, which is the whole point.
    result_bad = reconcile_load(batches_bad, batches_bad, batches_bad, SOURCE_CONFIG, run_id_bad, engine=engine)
    alert = latest_alert(engine, run_id_bad)

    print(f"  expected_rows={result_bad['raw_rows']} approved_rows={result_bad['approved_rows']} actual_rows={result_bad['actual_rows']} "
          f"matched={result_bad['matched']}")

    print("\n" + "=" * 60)
    print("RECONCILIATION CHECK")
    print("=" * 60)
    print(f"Happy path matched          : {result_ok['matched']}  (expected True)")
    print(f"Injected-mismatch matched   : {result_bad['matched']}  (expected False)")
    print(f"Alert written for mismatch  : {alert.severity if alert else None}")

    cleanup(engine)

    if result_ok["matched"] and not result_bad["matched"] and alert and alert.severity == "CRITICAL":
        print("\nPASS: reconciliation matched the healthy load and caught the")
        print("      deliberately-injected silent partial failure, alerting CRITICAL.")
    else:
        print("\nFAIL: reconciliation did not behave as expected.")
        sys.exit(1)


if __name__ == "__main__":
    main()
