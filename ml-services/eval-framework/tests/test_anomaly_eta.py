import pytest

from eval_framework.anomaly import (
    event_scores, find_events, pr_auc, precision_at_k, threshold_metrics,
)
from eval_framework.eta import interval_coverage, mae_by_horizon
from eval_framework.metrics import (
    HIGHER_IS_BETTER_METRICS, KNOWN_METRICS, LOWER_IS_BETTER_METRICS,
    TARGET_METRICS, mae,
)

Y = [1, 0, 1, 0]
S = [0.9, 0.8, 0.7, 0.1]


# ---------- registry ----------
def test_registry_new_metrics_and_target_kept_out_of_known():
    assert "pr_auc" in HIGHER_IS_BETTER_METRICS
    assert "mae" in LOWER_IS_BETTER_METRICS
    assert "interval_coverage" in TARGET_METRICS
    assert "interval_coverage" not in KNOWN_METRICS
    assert not (HIGHER_IS_BETTER_METRICS & LOWER_IS_BETTER_METRICS)


# ---------- mae ----------
def test_mae_known_answer():
    assert mae([1, 2, 3], [2, 2, 5]) == pytest.approx(1.0)  # (1+0+2)/3


@pytest.mark.parametrize("a,p", [([], []), ([1, 2], [1]), ([1, float("nan")], [1, 2]),
                                 ([1, float("inf")], [1, 2])])
def test_mae_rejects_bad_input(a, p):
    with pytest.raises(ValueError):
        mae(a, p)


# ---------- threshold metrics ----------
def test_threshold_metrics_known_answers():
    r = threshold_metrics(Y, S, 0.75)  # flags [1,1,0,0]: tp1 fp1 fn1
    assert (r["precision"], r["recall"], r["f1"]) == pytest.approx((0.5, 0.5, 0.5))
    r = threshold_metrics(Y, S, 0.7)   # >= inclusive: flags [1,1,1,0]
    assert r["precision"] == pytest.approx(2 / 3)
    assert r["recall"] == pytest.approx(1.0)
    assert r["f1"] == pytest.approx(0.8)


def test_threshold_metrics_nothing_flagged():
    r = threshold_metrics(Y, S, 0.95)
    assert r["n_flagged"] == 0 and r["precision"] == 0.0 and r["recall"] == 0.0


@pytest.mark.parametrize("thr", [None, float("nan"), float("inf"), "abc"])
def test_threshold_metrics_bad_threshold(thr):
    with pytest.raises(ValueError):
        threshold_metrics(Y, S, thr)


def test_threshold_metrics_bad_inputs():
    with pytest.raises(ValueError):
        threshold_metrics(Y, S[:3], 0.5)
    with pytest.raises(ValueError):
        threshold_metrics(Y, [0.9, float("nan"), 0.7, 0.1], 0.5)
    with pytest.raises(ValueError):
        threshold_metrics([-1, 1, -1, 1], S, 0.5)
    with pytest.raises(ValueError):
        threshold_metrics([], [], 0.5)


# ---------- PR-AUC ----------
def test_pr_auc_known_answer():
    # P/R points: (1,.5) (.5,.5) (2/3,1) (.5,1) -> .5*1 + 0 + .5*(2/3) = 5/6
    assert pr_auc(Y, S) == pytest.approx(5 / 6)


def test_pr_auc_perfect_ranking_is_one():
    assert pr_auc([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1]) == pytest.approx(1.0)


def test_pr_auc_all_tied_equals_prevalence():
    assert pr_auc([1, 0, 0, 0], [0.5] * 4) == pytest.approx(0.25)


def test_pr_auc_tie_order_independent():
    assert pr_auc([1, 0, 0, 0], [0.5] * 4) == pr_auc([0, 0, 0, 1], [0.5] * 4)


def test_pr_auc_no_positives_raises():
    with pytest.raises(ValueError):
        pr_auc([0, 0, 0], [0.1, 0.2, 0.3])


def test_pr_auc_bad_inputs():
    with pytest.raises(ValueError):
        pr_auc([1, 0], [0.1])
    with pytest.raises(ValueError):
        pr_auc([1, 0], [float("inf"), 0.1])


# ---------- precision@k ----------
def test_precision_at_k_known_answers():
    y = [1, 0, 1, 0, 0]
    s = [0.9, 0.8, 0.7, 0.2, 0.1]
    assert precision_at_k(y, s, 1) == pytest.approx(1.0)
    assert precision_at_k(y, s, 3) == pytest.approx(2 / 3)
    assert precision_at_k(y, s, 5) == pytest.approx(2 / 5)


@pytest.mark.parametrize("k", [0, -1, 6, 2.5, True, None])
def test_precision_at_k_bad_k(k):
    with pytest.raises(ValueError):
        precision_at_k([1, 0, 1, 0, 0], [0.9, 0.8, 0.7, 0.2, 0.1], k)


def test_precision_at_k_tie_straddling_boundary():
    y, s = [1, 0, 0], [0.9, 0.5, 0.5]
    with pytest.raises(ValueError):
        precision_at_k(y, s, 2)
    assert precision_at_k(y, s, 2, on_tie="first") == pytest.approx(0.5)
    assert precision_at_k(y, s, 1) == pytest.approx(1.0)  # tie not on boundary
    assert precision_at_k(y, s, 3) == pytest.approx(1 / 3)  # k == n, no boundary


def test_precision_at_k_bad_on_tie():
    with pytest.raises(ValueError):
        precision_at_k(Y, S, 2, on_tie="guess")


# ---------- events ----------
def test_find_events():
    assert find_events([0, 1, 1, 0, 1, 0, 0, 1, 1, 1]) == [(1, 2), (4, 4), (7, 9)]
    assert find_events([1, 1, 1]) == [(0, 2)]
    assert find_events([0, 0, 0]) == []


TRUE = [0, 1, 1, 1, 1, 0, 0, 0, 1, 1, 0, 0]   # events (1,4), (8,9)
PRED = [0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0]   # runs (2,2), (6,6)


def test_event_scores_known_answer_vs_point_level():
    r = event_scores(TRUE, PRED)
    assert r["n_true_events"] == 2 and r["n_pred_events"] == 2
    assert r["events_detected"] == 1 and r["false_alarm_events"] == 1
    assert r["event_recall"] == pytest.approx(0.5)
    assert r["event_precision"] == pytest.approx(0.5)
    assert r["event_f1"] == pytest.approx(0.5)


def test_event_scores_tolerance():
    r = event_scores(TRUE, PRED, tolerance=2)  # (6,6) now within [6,11] of event 2
    assert r["event_recall"] == pytest.approx(1.0)
    assert r["event_precision"] == pytest.approx(1.0)
    r = event_scores(TRUE, PRED, tolerance=1)  # window [7,10] still misses (6,6)
    assert r["event_recall"] == pytest.approx(0.5)


def test_event_scores_long_event_counts_once():
    y_true = [0] * 5 + [1] * 10 + [0] * 5
    r = event_scores(y_true, y_true)
    assert r["n_true_events"] == 1 and r["event_recall"] == 1.0 and r["event_f1"] == 1.0


def test_event_scores_false_alarm_burst_counts_once():
    y_true = [0] * 10
    y_pred = [0, 1, 1, 1, 1, 0, 0, 0, 0, 0]
    r = event_scores(y_true, y_pred)
    assert r["false_alarm_events"] == 1
    assert r["event_recall"] is None and r["event_f1"] is None  # no true events


def test_event_scores_nothing_predicted():
    r = event_scores([0, 1, 1, 0], [0, 0, 0, 0])
    assert r["event_precision"] is None and r["event_recall"] == 0.0
    assert r["event_f1"] is None


def test_event_scores_zero_f1_when_all_wrong():
    r = event_scores([1, 1, 0, 0, 0, 0], [0, 0, 0, 0, 1, 1])
    assert r["event_precision"] == 0.0 and r["event_recall"] == 0.0 and r["event_f1"] == 0.0


def test_event_scores_bad_inputs():
    with pytest.raises(ValueError):
        event_scores([1, 0], [1])
    with pytest.raises(ValueError):
        event_scores([1, 0], [1, 0], tolerance=-1)
    with pytest.raises(ValueError):
        event_scores([1, 0], [1, 0], tolerance=1.5)
    with pytest.raises(ValueError):
        event_scores([], [])
    with pytest.raises(ValueError):
        event_scores([1, 2], [1, 0])


# ---------- ETA: MAE by horizon ----------
YT = [10, 10, 10, 10]
YP = [11, 9, 13, 7]
H = [1, 1, 2, 2]


def test_mae_by_horizon_exact():
    r = mae_by_horizon(YT, YP, H)
    assert r["overall_mae"] == pytest.approx(2.0)
    assert r["by_horizon"][1] == {"mae": pytest.approx(1.0), "n": 2}
    assert r["by_horizon"][2] == {"mae": pytest.approx(3.0), "n": 2}


def test_mae_by_horizon_bins():
    r = mae_by_horizon(YT, YP, H, bins=[1, 2, 3])
    assert r["by_horizon"]["[1, 2)"]["mae"] == pytest.approx(1.0)
    assert r["by_horizon"]["[2, 3]"]["mae"] == pytest.approx(3.0)


def test_mae_by_horizon_bad_inputs():
    with pytest.raises(ValueError):
        mae_by_horizon(YT, YP, [1, 1, 2, 9], bins=[1, 2, 3])   # outside bins
    with pytest.raises(ValueError):
        mae_by_horizon(YT, YP, H, bins=[3, 2, 1])              # not increasing
    with pytest.raises(ValueError):
        mae_by_horizon(YT, YP, H[:3])
    with pytest.raises(ValueError):
        mae_by_horizon(YT, YP, [1, 1, 2, float("nan")])
    with pytest.raises(ValueError):
        mae_by_horizon([], [], [])


# ---------- ETA: interval coverage ----------
def test_interval_coverage_known_answer():
    y = [1, 2, 3, 4, 5]
    lo = [0, 3, 2, 5, 4]
    hi = [2, 4, 4, 6, 6]
    r = interval_coverage(y, lo, hi)  # inside: yes,no,yes,no,yes
    assert r["interval_coverage"] == pytest.approx(0.6)
    assert r["mean_interval_width"] == pytest.approx(1.6)  # (2+1+2+1+2)/5
    r = interval_coverage(y, lo, hi, nominal=0.9)
    assert r["coverage_gap"] == pytest.approx(-0.3)


def test_interval_coverage_boundary_inclusive():
    assert interval_coverage([1.0], [1.0], [1.0])["interval_coverage"] == 1.0


def test_interval_coverage_wide_intervals_expose_width():
    r = interval_coverage([1, 2, 3], [-1e6] * 3, [1e6] * 3)
    assert r["interval_coverage"] == 1.0 and r["mean_interval_width"] == pytest.approx(2e6)


def test_interval_coverage_bad_inputs():
    with pytest.raises(ValueError):
        interval_coverage([1, 2], [0, 5], [2, 4])              # inverted
    with pytest.raises(ValueError):
        interval_coverage([1, 2], [0], [2, 4])
    with pytest.raises(ValueError):
        interval_coverage([1, float("nan")], [0, 0], [2, 2])
    with pytest.raises(ValueError):
        interval_coverage([1, 2], [0, 0], [2, 2], nominal=1.5)
    with pytest.raises(ValueError):
        interval_coverage([], [], [])