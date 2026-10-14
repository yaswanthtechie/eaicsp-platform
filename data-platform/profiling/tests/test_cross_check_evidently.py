import pytest
from cross_check_evidently import (
    create_datasets,
    run_custom_drift,
    run_evidently_drift,
)


def get_evidently_dataset_drift(evidently_report):
    """Extract dataset drift status from Evidently 0.7.x metrics."""
    for metric in evidently_report.get("metrics", []):
        metric_name = str(metric.get("metric_name", ""))

        if metric_name.startswith("DriftedColumnsCount"):
            value = metric.get("value", {})

            if isinstance(value, dict):
                share = value.get("share")
                if share is not None:
                    return share >= 0.5

    raise AssertionError(
        "DriftedColumnsCount metric not found. "
        "Inspect the Evidently report structure."
    )


def get_evidently_drifted_columns_count(evidently_report):
    """Extract the number of drifted columns from Evidently 0.7.x."""
    for metric in evidently_report.get("metrics", []):
        metric_name = str(metric.get("metric_name", ""))

        if metric_name.startswith("DriftedColumnsCount"):
            value = metric.get("value", {})

            if isinstance(value, dict):
                return value.get("count", 0)

    raise AssertionError(
        "DriftedColumnsCount metric not found. "
        "Inspect the Evidently report structure."
    )


@pytest.fixture
def datasets():
    return create_datasets()


@pytest.mark.integration
def test_no_drift_agreement(datasets):
    baseline, no_drift, _ = datasets

    # Run custom drift
    custom_report = run_custom_drift(baseline, no_drift)
    assert custom_report["status"] == "No Drift"

    # Run Evidently drift
    evidently_report = run_evidently_drift(baseline, no_drift)

    # Extract Evidently dataset drift status safely
    dataset_drift = get_evidently_dataset_drift(evidently_report)

    assert dataset_drift is False, "Evidently incorrectly detected drift on identical datasets"


@pytest.mark.integration
def test_deliberate_drift_detection(datasets):
    baseline, _, drifted = datasets

    # Run custom drift
    custom_report = run_custom_drift(baseline, drifted)

    # Custom tool should catch the mean shift in unit_price and the null injection
    assert custom_report["status"] in ["Minor Drift", "Major Drift"]
    assert custom_report["column_drift"]["unit_price"]["status"] != "no_drift"

    # Run Evidently drift
    evidently_report = run_evidently_drift(baseline, drifted)

    # Extract Evidently dataset drift status safely
    dataset_drift = get_evidently_dataset_drift(evidently_report)
    drifted_columns = get_evidently_drifted_columns_count(evidently_report)

    assert dataset_drift is True, "Evidently failed to detect the deliberate dataset drift"
    assert drifted_columns > 0, "Evidently did not flag any individual columns as drifted"