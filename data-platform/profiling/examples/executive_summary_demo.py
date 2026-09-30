from pathlib import Path
import json

import pandas as pd

from src.profiler import Profiler


def main():
    profiler = Profiler()

    # ---------------------------------
    # 1. Profile the actual project data
    # ---------------------------------
    data_path = Path("data/sales_data.csv")
    df = pd.read_csv(data_path)

    profiling_report = profiler.profile(df)

    # ---------------------------------
    # 2. Create demo static ETL output
    # ---------------------------------
    etl_output_path = Path("reports/demo_etl_output.json")

    etl_output = {
        "status": "success",
        "warnings": 1,
        "errors": 0,
        "sla_status": "met",
    }

    etl_output_path.write_text(
        json.dumps(etl_output, indent=2),
        encoding="utf-8",
    )

    # ---------------------------------
    # 3. Create demo static validation output
    # ---------------------------------
    validation_output_path = Path(
        "reports/demo_validation_output.json"
    )

    validation_output = {
        "status": "pass",
        "invalid_rows": 3,
        "validation_failures": 1,
        "errors": 0,
        "warnings": 1,
    }

    validation_output_path.write_text(
        json.dumps(validation_output, indent=2),
        encoding="utf-8",
    )

    # ---------------------------------
    # 4. Generate executive summary
    #    by reading static JSON files
    # ---------------------------------
    summary = profiler.executive_summary(
        profiling_report=profiling_report,
        etl_output=etl_output_path,
        validation_output=validation_output_path,
    )

    # ---------------------------------
    # 5. Save final summary
    # ---------------------------------
    summary_path = Path(
        "reports/executive_summary.txt"
    )

    summary_path.write_text(
        summary,
        encoding="utf-8",
    )

    print("Executive Summary:")
    print(summary)
    print()
    print(f"Saved to: {summary_path}")


if __name__ == "__main__":
    main()