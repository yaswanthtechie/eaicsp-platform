import json
import pandas as pd

from src.profiler import Profiler


def test_monitoring_history(tmp_path):
    old_df = pd.DataFrame({
        "sku_id": ["SKU001", "SKU002", "SKU003"],
        "quantity_sold": [10, 20, 30]
    })

    new_df = pd.DataFrame({
        "sku_id": ["SKU001", "SKU002", "SKU004"],
        "quantity_sold": [10, 20, 30]
    })

    profiler = Profiler()

    # Use temporary history file so the test
    # does not modify the real reports/history.json
    from src.monitoring import MonitoringHistory

    history_file = tmp_path / "history.json"

    monitoring = MonitoringHistory(
        history_file=str(history_file),
        max_batches=10
    )

    report = profiler.profile(old_df)
    monitoring.save_batch(report)

    new_report = profiler.profile(new_df)
    drift = profiler.compare(old_df, new_df)

    history = monitoring.save_batch(
        new_report,
        drift
    )

    assert len(history) == 2
    assert history[0]["drift_status"] == "No Previous Batch"
    assert history[1]["drift_status"] in [
        "No Drift",
        "Minor Drift",
        "Major Drift"
    ]

    # Verify actual JSON file
    with open(history_file, "r") as file:
        saved_history = json.load(file)

    assert len(saved_history) == 2

def test_monitoring_keeps_last_10_batches(tmp_path):
    from src.monitoring import MonitoringHistory

    history_file = tmp_path / "history.json"

    monitoring = MonitoringHistory(
        history_file=str(history_file),
        max_batches=10
    )

    # Save 12 fake batches
    for i in range(12):
        report = {
            "quality_score": {
                "score": 80 + i,
                "missing_values": 0,
                "duplicate_rows": 0,
                "total_outliers": 0
            }
        }

        monitoring.save_batch(report)

    history = monitoring.load_history()

    # Only latest 10 should remain
    assert len(history) == 10

    # First two batches should have been removed
    assert history[0]["quality_score"] == 82
    assert history[-1]["quality_score"] == 91


def test_quality_score_trend(tmp_path):
    from src.monitoring import MonitoringHistory

    history_file = tmp_path / "history.json"

    monitoring = MonitoringHistory(
        history_file=str(history_file),
        max_batches=10
    )

    # Quality scores improve over time
    scores = [60, 65, 70, 75]

    for score in scores:
        report = {
            "quality_score": {
                "score": score,
                "missing_values": 0,
                "duplicate_rows": 0,
                "total_outliers": 0
            }
        }

        monitoring.save_batch(report)

    trend = monitoring.get_trend()

    assert trend["batches"] == 4
    assert trend["quality_scores"] == [60, 65, 70, 75]
    assert trend["trend"] == "Improving"


def test_column_null_rate_trend(tmp_path):
    from src.monitoring import MonitoringHistory

    history_file = tmp_path / "history.json"

    monitoring = MonitoringHistory(
        history_file=str(history_file),
        max_batches=10
    )

    reports = [2.0, 3.5, 4.0]

    for null_rate in reports:
        report = {
            "quality_score": {
                "score": 90,
                "missing_values": 0,
                "duplicate_rows": 0,
                "total_outliers": 0
            },
            "column_summary": [
                {
                    "column": "quantity_sold",
                    "null_percent": null_rate
                }
            ]
        }

        monitoring.save_batch(report)

    trend = monitoring.get_column_trend("quantity_sold")

    assert trend["column"] == "quantity_sold"
    assert trend["values"] == [2.0, 3.5, 4.0]
