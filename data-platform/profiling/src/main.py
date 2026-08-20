from pathlib import Path

import pandas as pd

from src.make_sample_data import make_sample_data
from src.profile import profile, generate_html
from src.monitoring import MonitoringHistory
from src.report import generate_report
from src.scheduled_report import check_quality_threshold


def main():
    print("=" * 60)
    print("STARTING DATA PROFILING PROJECT")
    print("=" * 60)

    # Generate sample data
    make_sample_data()

    # Load and profile the current dataset
    base_dir = Path(__file__).resolve().parent.parent
    data_path = base_dir / "data" / "sales_data.csv"

    df = pd.read_csv(data_path)
    report = profile(df)

    # Save current profiling run to historical monitoring
    monitoring = MonitoringHistory()
    monitoring.save_batch(report)

    # Scheduled quality check mock
    quality_check = check_quality_threshold(
        report,
        threshold=80
    )

    print(
        f"SCHEDULED QUALITY CHECK: "
        f"{quality_check['status']} - "
        f"{quality_check['message']}"
    )

    # Generate HTML report including historical trends
    generate_html(report=report)

    # Generate standard data-quality report
    generate_report()

    print("=" * 60)
    print("PROJECT COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()