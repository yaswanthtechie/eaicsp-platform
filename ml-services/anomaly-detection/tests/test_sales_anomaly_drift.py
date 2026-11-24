"""
Data drift check: a shifted sample triggers the alert, a fresh sample of the
same data does not, and thresholds come from the arguments (config defaults).
"""

import numpy as np
import pandas as pd
import pytest

from src import config
from src.sales_anomaly_drift import (
    COLUMNS,
    check_drift,
    drift_frame,
    latest_window,
)


def make_scores(seed, mean=50.0, zero_share=0.02, days=60, series=20):
    """A detect()-like frame: one row per series and day, with a quantity."""

    rng = np.random.default_rng(seed)
    dates = pd.date_range("2026-01-01", periods=days, freq="D")
    n = days * series

    quantity = rng.poisson(rng.gamma(8, mean / 8, n)).astype(float)
    quantity[rng.random(n) < zero_share] = 0.0

    return pd.DataFrame(
        {
            "product": np.repeat([f"SKU-{i:06d}" for i in range(series)], days),
            "date": np.tile(dates, series),
            "quantity": quantity,
        }
    )


@pytest.fixture(scope="module")
def reference():
    return make_scores(seed=1)


# ---------------------------------------------------------------------
# the alert
# ---------------------------------------------------------------------


def test_a_new_sample_of_the_same_data_does_not_alert(reference):

    result = check_drift(reference, make_scores(seed=2))

    assert not result.alert
    assert result.drift_share == 0
    assert not any(info["drift"] for info in result.columns.values())


def test_a_shifted_quantity_distribution_alerts(reference):

    result = check_drift(reference, make_scores(seed=3, mean=150))

    assert result.alert
    assert result.columns["quantity"]["drift"]
    assert result.drift_share == 0.5
    assert result.latest_mean_quantity > 2 * result.reference_mean_quantity


def test_more_zero_sales_days_alert(reference):

    result = check_drift(reference, make_scores(seed=4, zero_share=0.30))

    assert result.alert
    assert result.columns["zero_sales_day"]["drift"]
    assert result.reference_zero_share < 0.05
    assert result.latest_zero_share > 0.25


def test_both_columns_can_drift_together(reference):

    result = check_drift(reference, make_scores(seed=5, mean=150, zero_share=0.30))

    assert result.alert
    assert result.drift_share == 1.0


def test_the_result_covers_exactly_the_two_columns(reference):

    result = check_drift(reference, make_scores(seed=6))

    assert set(result.columns) == set(COLUMNS) == {"quantity", "zero_sales_day"}
    assert all(info["score"] is not None for info in result.columns.values())


# ---------------------------------------------------------------------
# thresholds are configurable
# ---------------------------------------------------------------------


def test_a_higher_drift_threshold_lets_the_shift_through(reference):

    shifted = make_scores(seed=3, mean=150)

    assert check_drift(reference, shifted).alert
    assert not check_drift(reference, shifted, num_threshold=50).alert


def test_alert_share_decides_how_many_columns_must_drift(reference):

    shifted = make_scores(seed=3, mean=150)  # only the quantity drifts

    assert check_drift(reference, shifted, alert_share=0.5).alert
    assert not check_drift(reference, shifted, alert_share=1.0).alert


def test_defaults_come_from_config():

    assert config.DRIFT_NUM_THRESHOLD == 0.1
    assert config.DRIFT_CAT_THRESHOLD == 0.1
    assert config.DRIFT_ALERT_SHARE == 0.5
    assert config.DRIFT_LATEST_DAYS == 28


# ---------------------------------------------------------------------
# what is logged
# ---------------------------------------------------------------------


def test_metrics_and_message(reference):

    result = check_drift(reference, make_scores(seed=3, mean=150))
    metrics = result.metrics()

    for key in (
        "drift_share",
        "drift_alert",
        "drift_score_quantity",
        "drift_score_zero_sales_day",
        "zero_share_reference",
        "zero_share_latest",
        "mean_quantity_reference",
        "mean_quantity_latest",
    ):
        assert key in metrics, key

    assert metrics["drift_alert"] == 1.0
    assert "1 of 2 columns drifted (quantity)" in result.message()
    assert "zero-sales days" in result.message()


def test_the_html_report_is_returned(reference):

    result = check_drift(reference, make_scores(seed=2))

    assert len(result.html) > 1000
    assert "quantity" in result.html


# ---------------------------------------------------------------------
# input handling
# ---------------------------------------------------------------------


def test_latest_window_is_the_last_days(reference):

    window = latest_window(reference, days=28)

    assert window["date"].nunique() == 28
    assert window["date"].max() == reference["date"].max()


def test_latest_window_of_nothing_is_nothing(reference):

    assert latest_window(reference.iloc[0:0]).empty


def test_feed_gap_days_without_a_quantity_are_left_out():

    scores = make_scores(seed=1, days=10, series=2)
    scores.loc[scores.index[:5], "quantity"] = np.nan

    assert len(drift_frame(scores)) == len(scores) - 5


def test_big_frames_are_sampled_to_the_row_limit():

    scores = make_scores(seed=1, days=60, series=20)

    assert len(drift_frame(scores, max_rows=300)) == 300
    assert len(drift_frame(scores, max_rows=300)) == len(
        drift_frame(scores, max_rows=300)
    )


def test_a_side_with_no_days_is_an_error(reference):

    with pytest.raises(ValueError):
        check_drift(reference, reference.iloc[0:0])

    with pytest.raises(ValueError):
        check_drift(reference.iloc[0:0], reference)


def test_no_zero_days_on_either_side_still_works():

    ref = make_scores(seed=1, zero_share=0.0)
    ref.loc[ref["quantity"] == 0, "quantity"] = 1.0

    result = check_drift(
        ref,
        make_scores(seed=2, zero_share=0.0).assign(
            quantity=lambda f: f["quantity"].clip(lower=1)
        ),
    )

    assert result.reference_zero_share == 0
    assert result.latest_zero_share == 0


# ---------------------------------------------------------------------
# the threshold means the same on a small reference
# ---------------------------------------------------------------------


def test_a_reference_under_1000_rows_uses_the_same_distance_measures():
    """Evidently switches to p-value tests under 1,000 rows unless the method is fixed."""

    small = make_scores(seed=1, days=45, series=20)  # 900 rows

    assert len(small) == 900

    # A huge threshold cannot raise an alert on identical data (with a p-value
    # test, it did).
    for seed in range(2, 8):
        result = check_drift(
            small, make_scores(seed=seed, days=45, series=20), num_threshold=50
        )

        assert not result.alert, seed


def test_identical_distributions_rarely_alert_on_a_small_reference():

    small = make_scores(seed=1, days=45, series=20)

    alerts = sum(
        check_drift(small, make_scores(seed=seed, days=45, series=20)).alert
        for seed in range(10, 30)
    )

    assert alerts <= 2


def test_a_shifted_sample_still_alerts_on_a_small_reference():

    small = make_scores(seed=1, days=45, series=20)

    assert check_drift(small, make_scores(seed=3, days=45, series=20, mean=150)).alert


def test_a_higher_threshold_never_makes_an_alert_more_likely_on_a_small_reference():

    small = make_scores(seed=1, days=45, series=20)
    latest = make_scores(seed=3, days=45, series=20, mean=70)

    alerts = [
        check_drift(small, latest, num_threshold=t).alert for t in (0.05, 0.2, 0.8, 5)
    ]

    assert alerts == sorted(alerts, reverse=True)
