"""
Milestone 4 - ETA error vs anomaly flag correlation analysis.

The method is validated on synthetic worlds where the truth is known:
it must stay quiet when there is no relationship and find one when
there is.
"""

import pandas as pd
import pytest

from src.eta_anomaly_correlation import (
    analyze_correlation,
    effect_label,
    join_eta_and_anomaly,
    make_synthetic_joint,
)


FAST = {"n_bootstrap": 300, "n_permutations": 300}


def test_null_world_is_not_flagged_as_association():
    false_positives = 0

    for seed in range(10):
        frame = make_synthetic_joint(coupling=0.0, seed=seed)
        verdict = analyze_correlation(frame, **FAST)["verdict"]

        false_positives += verdict == "association_detected"

    # alpha = 0.05 and an effect-size gate: expect about zero.
    assert false_positives <= 1


def test_coupled_world_is_detected():
    frame = make_synthetic_joint(coupling=1.5, seed=1)

    result = analyze_correlation(frame, **FAST)

    assert result["verdict"] == "association_detected"
    assert result["median_difference"] > 0
    assert result["median_difference_ci95"][0] > 0
    assert result["point_biserial_r"] > 0


def test_report_contains_every_statistic():
    result = analyze_correlation(make_synthetic_joint(seed=2), **FAST)

    for key in (
        "n",
        "n_flagged",
        "mann_whitney_p",
        "cliffs_delta",
        "effect_size",
        "point_biserial_r",
        "permutation_p",
        "median_difference_ci95",
        "min_detectable_delta_80pct_power",
        "score_spearman_rho",
        "summary",
    ):
        assert key in result


def test_null_summary_states_what_cannot_be_ruled_out():
    result = analyze_correlation(
        make_synthetic_joint(coupling=0.0, seed=3), **FAST
    )

    if result["verdict"] == "no_association_detected":
        assert "could not be reliably detected" in result["summary"]


def test_too_few_flagged_rows_is_insufficient_data():
    frame = make_synthetic_joint(n=200, anomaly_rate=0.01, seed=4)

    result = analyze_correlation(frame, min_group=10, **FAST)

    assert result["verdict"] == "insufficient_data"


def test_analysis_is_reproducible():
    frame = make_synthetic_joint(seed=5)

    assert analyze_correlation(frame, **FAST) == analyze_correlation(
        frame, **FAST
    )


def test_join_matches_on_key_and_drops_unmatched():
    eta = pd.DataFrame({"shipment_id": [1, 2, 3], "eta_error": [5, -3, 9]})
    anomaly = pd.DataFrame(
        {"shipment_id": [2, 3, 4], "is_anomaly": [0, 1, 1], "score": [0.1, 0.9, 0.8]}
    )

    joined = join_eta_and_anomaly(
        eta, anomaly, key="shipment_id", score_col="score"
    )

    assert list(joined["shipment_id"]) == [2, 3]
    assert "anomaly_score" in joined.columns


def test_join_with_no_shared_keys_raises_instead_of_hiding_it():
    eta = pd.DataFrame({"k": [1], "eta_error": [1.0]})
    anomaly = pd.DataFrame({"k": [2], "is_anomaly": [1]})

    with pytest.raises(ValueError):
        join_eta_and_anomaly(eta, anomaly, key="k")


def test_join_reports_missing_columns():
    with pytest.raises(ValueError):
        join_eta_and_anomaly(
            pd.DataFrame({"k": [1]}),
            pd.DataFrame({"k": [1], "is_anomaly": [1]}),
            key="k",
        )


def test_analyze_rejects_missing_columns():
    with pytest.raises(ValueError):
        analyze_correlation(pd.DataFrame({"eta_error": [1.0]}))


def test_effect_labels():
    assert effect_label(0.05) == "negligible"
    assert effect_label(-0.2) == "small"
    assert effect_label(0.4) == "medium"
    assert effect_label(0.9) == "large"