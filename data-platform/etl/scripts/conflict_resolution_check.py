"""
R5 #1: Conflict resolution proof - two competing files, one run.

Simulates the exact scenario in the spec: an original sales file and a
same-day correction file, both claiming to update the same
(date, sku_id, warehouse_id) row with different values, loaded in the same
run. Proves the winner is decided by the explicit "latest file wins" rule
(filename version/timestamp priority), not by whichever file bulk_upsert() happened to
process last.

The test is deliberately adversarial: the ORIGINAL file is named so it
sorts AFTER the correction file alphabetically (extract_data() globs and
sorts filenames), so if the pipeline were still relying on accidental
processing order, the ORIGINAL (stale) value would win. The correction
file's explicit filename priority is higher, so the explicit rule must pick the correction's
value instead.

Runs against a disposable scratch table so it never touches real sales_fact.

Usage:
    cd etl/src && python3 ../../scripts/conflict_resolution_check.py
"""

import os
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "etl" / "src"))
os.chdir(REPO_ROOT)

import pandas as pd
from sqlalchemy import text

from database import get_engine
from load import bulk_upsert, source_file_priority


TABLE = "sales_fact_conflict_check"


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


def main():
    engine = get_engine()

    # --- Build two competing "files" for the same row ------------------
    #
    # "aaa" sorts BEFORE "zzz" alphabetically, so extract_data()'s
    # sorted(glob(...)) processes the correction file FIRST and the stale
    # original LAST. A naive "just keep whatever record comes last in
    # processing order" dedupe (the old behavior, still the default when no
    # priority_key is given) would therefore incorrectly keep the STALE
    # value. The correction file gets the NEWER explicit filename priority; the explicit
    # "latest file wins" rule must override naive order and keep the
    # correction's value instead.
    tmp_dir = REPO_ROOT / "data" / "batches" / "_conflict_check_scratch"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    correction_file = tmp_dir / "sales_2024-06-01__v2_aaa_correction.csv"  # sorts FIRST, explicit filename priority NEWER
    stale_file = tmp_dir / "sales_2024-06-01__v1_zzz_original.csv"         # sorts LAST, explicit filename priority OLDER

    pd.DataFrame([{
        "date": "2024-06-01", "sku_id": "SKU777", "warehouse_id": "WH1",
        "quantity_sold": 250, "unit_price": 10.00,
    }]).to_csv(correction_file, index=False)

    pd.DataFrame([{
        "date": "2024-06-01", "sku_id": "SKU777", "warehouse_id": "WH1",
        "quantity_sold": 5, "unit_price": 10.00,
    }]).to_csv(stale_file, index=False)


    files_in_process_order = sorted(tmp_dir.glob("*.csv"))
    print("Files, in the order extract_data() would process them (sorted by name):")
    for f in files_in_process_order:
        print(f"  {f.name}")
    naive_winner = files_in_process_order[-1].name
    print(f"Under naive 'last file processed wins': {naive_winner} would incorrectly win.\n")

    # --- Build records exactly like load_data_bulk_generic() does ------
    records = []
    for f in files_in_process_order:
        df = pd.read_csv(f)
        priority = source_file_priority(f)
        for record in df.to_dict(orient="records"):
            record["source_batch"] = f.name
            record["run_id"] = 999
            record["pipeline_version"] = "1.0.0"
            record["_conflict_priority"] = priority
            records.append(record)

    columns = [
        "date", "sku_id", "warehouse_id", "quantity_sold", "unit_price",
        "source_batch", "run_id", "pipeline_version",
    ]

    setup_scratch_table(engine)

    bulk_upsert(
        engine=engine,
        table_name=TABLE,
        columns=columns,
        conflict_keys=["date", "sku_id", "warehouse_id"],
        records=records,
        priority_key="_conflict_priority",
    )

    with engine.connect() as conn:
        row = conn.execute(text(f"""
            SELECT quantity_sold, source_batch FROM {TABLE}
            WHERE date = :d AND sku_id = :s AND warehouse_id = :w
        """), {"d": date(2024, 6, 1), "s": "SKU777", "w": "WH1"}).fetchone()

    teardown_scratch_table(engine)
    for f in tmp_dir.glob("*.csv"):
        f.unlink()
    tmp_dir.rmdir()

    print("=" * 60)
    print("CONFLICT RESOLUTION CHECK")
    print("=" * 60)
    print(f"Loaded quantity_sold : {row.quantity_sold}")
    print(f"Winning source file  : {row.source_batch}")
    print(f"Expected (newest explicit filename priority, the correction): 250 / {correction_file.name}")

    if row.quantity_sold == 250 and row.source_batch == correction_file.name:
        print("\nPASS: explicit 'latest file wins' rule was applied correctly,")
        print("      even though naive processing order would have picked the wrong file.")
    else:
        print("\nFAIL: conflict was resolved by accidental order, not the explicit rule.")
        sys.exit(1)


if __name__ == "__main__":
    main()
