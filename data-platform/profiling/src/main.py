from pathlib import Path

import pandas as pd

from src.make_sample_data import make_sample_data
from src.profile import profile, generate_html
from src.monitoring import MonitoringHistory
from src.report import generate_report
from src.scheduled_report import check_quality_threshold
from src.rules_suggestions import write_rules_yaml


def main():
    # Generate sample data
    print("Generating sample data...")
    make_sample_data()

    # Load and profile the current dataset
    base_dir = Path(__file__).resolve().parent.parent
    data_path = base_dir / "data" / "sales_data.csv"

    print("Profiling sales data...")
    df = pd.read_csv(data_path)
    report = profile(df)

    # Generate suggested data-quality rules
    print("Generating suggested data-quality rules...")
    write_rules_yaml(report)

    # Save current profiling run to historical monitoring
    print("Saving monitoring history...")
    monitoring = MonitoringHistory()
    monitoring.save_batch(report)

    # Compare recent quality-score runs
    monitoring_report = monitoring.compare_runs(
        "quality_score",
        last_n=10
    )

    # Check quality alert based on recent monitoring history
    quality_alert = monitoring.get_quality_alert()

    # Scheduled quality check mock
    quality_check = check_quality_threshold(
        report,
        threshold=80
    )

    # Generate HTML report including historical trends
    print("Generating HTML report...")
    generate_html(
        report=report,
        monitoring_report=monitoring_report
    )

    # Generate standard data-quality report
    print("Generating standard data-quality report...")
    generate_report()

    print("Quality alert:", quality_alert)
    print("Quality check:", quality_check)
    print("Data profiling completed successfully.")


if __name__ == "__main__":
    main()