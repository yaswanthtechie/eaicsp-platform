import pytest
from cross_check_evidently import (
    build_comparison, create_datasets, run_custom_drift,
    run_evidently_drift, summarize_evidently,
)


@pytest.fixture(scope="module")
def datasets():
    return create_datasets()


def test_no_drift_pair_agrees(datasets):
    baseline, no_drift, _ = datasets
    custom = run_custom_drift(baseline, no_drift)
    ev = summarize_evidently(run_evidently_drift(baseline, no_drift))
    assert custom["status"] == "No Drift"
    assert ev["dataset_drift"] is False


def test_deliberate_drift_detected_by_both(datasets):
    baseline, _, drifted = datasets
    custom = run_custom_drift(baseline, drifted)
    ev = summarize_evidently(run_evidently_drift(baseline, drifted))
    assert custom["column_drift"]["unit_price"]["status"] != "no_drift"
    assert ev["columns"]["unit_price"]["drift"] is True


def test_evidently_catches_variance_change_that_custom_misses(datasets):
    """The headline Milestone 3 finding. If this fails, update the README, not the test."""
    baseline, _, drifted = datasets
    custom = run_custom_drift(baseline, drifted)
    ev = summarize_evidently(run_evidently_drift(baseline, drifted))
    assert ev["columns"]["quantity_sold"]["drift"] is True
    assert custom["column_drift"]["quantity_sold"]["status"] == "no_drift"