from pathlib import Path

import pandas as pd

from src.profiler import Profiler


def main():
    base_dir = Path(__file__).resolve().parent.parent
    data_path = base_dir / "data" / "sales_data.csv"

    df = pd.read_csv(data_path)

    profiler = Profiler()

    result = profiler.monitor(df)

    audit_record = result["audit"]

    all_runs = profiler.query_audit_runs()

    print("=== Audit Archive Demo ===")
    print(f"Dataset rows: {len(df)}")
    print(f"Run ID: {audit_record['run_id']}")
    print(f"Run timestamp: {audit_record['timestamp']}")
    print(
        f"Quality score: "
        f"{audit_record['profile_report']['quality_score']['score']}"
    )
    print(f"Total archived runs: {len(all_runs)}")

    queried_run = profiler.query_audit_runs(
        min_quality_score=0,
        max_quality_score=100,
    )

    print(f"Queryable runs: {len(queried_run)}")


if __name__ == "__main__":
    main()