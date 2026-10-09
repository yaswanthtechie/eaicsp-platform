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

    Path("reports").mkdir(exist_ok=True)

    # ---------------------------------
    # 2. ETL output (PROPOSED CONTRACT - not yet published by the ETL)
    # ---------------------------------
    # Vivek's ETL does not publish a run-summary file yet; its results
    # live in the etl_run_log / etl_alerts tables and in logs. This is
    # the small file we have asked it to publish (see README, "ETL run
    # summary contract"). Until it exists, this sample stands in for it
    # and the summary is clearly a demo for the ETL part.
    etl_output_path = Path("reports/demo_etl_run_summary.json")

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
    # 3. Validation output (REAL - Tharun's published report)
    # ---------------------------------
    # Produced by data-platform/validation:
    #   python -m src.validate_cli --file tests/data/messy_sales_500.csv \
    #       --output <path> --config configs/sales_rules.yaml
    # We only read the file; we never import or call the validator.
    validation_output_path = Path(
        "tests/fixtures/validation_report_tharun.json"
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