import sys
import os
import json
import subprocess

import pandas as pd

EVAL_FRAMEWORK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, EVAL_FRAMEWORK_DIR)

from src.metrics import (
    mape, rmse, confusion_matrix, precision_recall, anomaly_metrics, accuracy
)
from src.baseline import naive_forecast, compare_to_baseline
from src.splits import time_based_split, walk_forward_split
from src.leaderboard import generate_leaderboard
from src.significance import paired_significance_test
from src.guardrails import (
    check_no_train_test_overlap, check_suspicious_accuracy,
    check_chronological_order, run_all_guardrails, LeakageError
)
from src.backtest import backtest
from src.report_html import generate_html_report, save_html_report
from fastapi.testclient import TestClient
from src.leaderboard_service import app

client = TestClient(app)


# ---------- metrics.py ----------

def test_mape():
    assert round(mape([100, 200], [110, 190]), 2) == 7.5


def test_rmse():
    assert round(rmse([100, 200], [110, 190]), 2) == 10.0


def test_mape_single_row():
    assert round(mape([100], [110]), 2) == 10.0


def test_confusion_matrix_basic():
    result = confusion_matrix([1, 0, 1, 0], [1, 0, 0, 0])
    assert result == {"tp": 1, "tn": 2, "fp": 0, "fn": 1}


def test_confusion_matrix_empty_raises():
    try:
        confusion_matrix([], [])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_confusion_matrix_rejects_sklearn_style_labels():
    try:
        confusion_matrix([1, -1], [1, -1])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "0 or 1" in str(e)


def test_precision_recall_all_same_class():
    result = precision_recall([1, 1, 0], [0, 0, 0])
    assert result["precision"] == 0.0
    assert result["recall"] == 0.0
    assert result["f1"] == 0.0


def test_precision_recall_perfect():
    result = precision_recall([1, 0, 1, 0], [1, 0, 1, 0])
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["f1"] == 1.0


def test_anomaly_metrics_basic():
    y_true = [0, 0, 0, 1, 0, 0, 0, 1, 0, 0]
    y_pred = [0, 0, 0, 1, 0, 0, 1, 0, 0, 0]
    result = anomaly_metrics(y_true, y_pred)
    assert result["recall"] == 0.5
    assert result["specificity"] == 0.875
    assert round(result["false_positive_rate"], 3) == 0.125
    assert round(result["balanced_accuracy"], 4) == 0.6875


def test_anomaly_metrics_includes_precision_and_f1():
    y_true = [0, 0, 0, 1, 0, 0, 0, 1, 0, 0]
    y_pred = [0, 0, 0, 1, 0, 0, 1, 0, 0, 0]
    result = anomaly_metrics(y_true, y_pred)
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["f1"] == 0.5


def test_anomaly_metrics_all_normal():
    y_true = [0, 0, 0, 0, 0]
    y_pred = [0, 0, 0, 0, 0]
    result = anomaly_metrics(y_true, y_pred)
    assert result["recall"] == 0.0
    assert result["specificity"] == 1.0
    assert result["false_positive_rate"] == 0.0
    assert result["balanced_accuracy"] == 0.5


def test_anomaly_metrics_all_anomaly():
    y_true = [1, 1, 1, 1]
    y_pred = [1, 1, 1, 1]
    result = anomaly_metrics(y_true, y_pred)
    assert result["recall"] == 1.0
    assert result["specificity"] == 0.0
    assert result["balanced_accuracy"] == 0.5


def test_anomaly_metrics_all_correct():
    y_true = [0, 1, 0, 1, 1]
    y_pred = [0, 1, 0, 1, 1]
    result = anomaly_metrics(y_true, y_pred)
    assert result["recall"] == 1.0
    assert result["specificity"] == 1.0
    assert result["false_positive_rate"] == 0.0
    assert result["balanced_accuracy"] == 1.0


def test_anomaly_metrics_all_wrong():
    y_true = [0, 1, 0, 1, 1]
    y_pred = [1, 0, 1, 0, 0]
    result = anomaly_metrics(y_true, y_pred)
    assert result["recall"] == 0.0
    assert result["specificity"] == 0.0
    assert result["false_positive_rate"] == 1.0
    assert result["balanced_accuracy"] == 0.0


def test_anomaly_metrics_rejects_sklearn_style_labels():
    try:
        anomaly_metrics([1, -1, 1, -1], [1, 1, -1, -1])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "-1" in str(e) or "unexpected value" in str(e)


def test_accuracy_basic():
    y_true = [0, 0, 0, 1, 0, 0, 0, 1, 0, 0]
    y_pred = [0, 0, 0, 1, 0, 0, 1, 0, 0, 0]
    assert accuracy(y_true, y_pred) == 0.8


def test_accuracy_perfect():
    y_true = [0, 1, 0, 1, 1]
    y_pred = [0, 1, 0, 1, 1]
    assert accuracy(y_true, y_pred) == 1.0


def test_accuracy_all_wrong():
    y_true = [0, 1, 0, 1]
    y_pred = [1, 0, 1, 0]
    assert accuracy(y_true, y_pred) == 0.0


# ---------- baseline.py ----------

def test_naive_forecast():
    assert naive_forecast([10, 20, 30, 40]) == [10, 10, 20, 30]


def test_compare_to_baseline():
    result = compare_to_baseline([100, 200], [110, 190], [100, 200])
    assert result["mape_winner"] == "model"


def test_compare_to_baseline_tie():
    result = compare_to_baseline([110, 190], [110, 190], [100, 200])
    assert result["mape_winner"] == "tie"
    assert result["mape_diff"] == 0
    assert result["rmse_winner"] == "tie"
    assert result["rmse_diff"] == 0


# ---------- splits.py ----------

def test_time_based_split_no_leakage():
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=10), "y": range(10)})
    train, test = time_based_split(df, "date", test_size=0.2)
    assert len(train) == 8 and len(test) == 2
    assert train["date"].max() < test["date"].min()


def test_walk_forward_split_basic():
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=20), "y": range(20)})
    folds = walk_forward_split(df, "date", n_splits=3)
    assert len(folds) == 3
    for train, test in folds:
        assert train["date"].max() < test["date"].min()


def test_walk_forward_split_too_little_data_raises():
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=1), "y": [1]})
    try:
        walk_forward_split(df, "date", n_splits=3)
        assert False, "expected ValueError"
    except ValueError:
        pass


# ---------- leaderboard.py ----------

def test_leaderboard_ranks_correctly():
    results = {"naive": {"mape": 6.80}, "prophet": {"mape": 3.20}, "xgboost": {"mape": 4.50}}
    ranked = generate_leaderboard(results, "mape", lower_is_better=True)
    assert ranked[0][0] == "prophet"
    assert ranked[-1][0] == "naive"


def test_leaderboard_higher_is_better():
    results = {"a": {"precision": 0.6}, "b": {"precision": 0.9}}
    ranked = generate_leaderboard(results, "precision", lower_is_better=False)
    assert ranked[0][0] == "b"


def test_leaderboard_refuses_incompatible_metrics():
    bad_results = {"naive": {"mape": 6.80}, "xgboost": {"precision": 0.9}}
    try:
        generate_leaderboard(bad_results, "mape")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "xgboost" in str(e)


def test_leaderboard_empty_results_raises():
    try:
        generate_leaderboard({}, "mape")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_leaderboard_single_model_raises():
    try:
        generate_leaderboard({"only_one": {"mape": 5.0}}, "mape")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_leaderboard_rejects_non_numeric_value():
    try:
        generate_leaderboard({"a": {"mape": "high"}, "b": {"mape": 3.2}}, "mape")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "a" in str(e)


def test_leaderboard_rejects_nan():
    try:
        generate_leaderboard({"a": {"mape": float("nan")}, "b": {"mape": 3.2}}, "mape")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "a" in str(e)


# ---------- significance.py ----------

def test_significance_detects_real_difference():
    scores_a = [3.1, 3.4, 2.9, 3.2, 3.0]
    scores_b = [6.8, 7.1, 6.5, 6.9, 7.0]
    result = paired_significance_test(scores_a, scores_b)
    assert result["significant"] is True


def test_significance_detects_no_difference():
    scores_a = [5.1, 4.8, 5.5, 5.0, 4.9]
    scores_b = [5.0, 5.2, 4.9, 5.1, 5.0]
    result = paired_significance_test(scores_a, scores_b)
    assert result["significant"] is False


def test_significance_mismatched_lengths_raises():
    try:
        paired_significance_test([1, 2, 3], [1, 2])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_significance_too_few_folds_raises():
    try:
        paired_significance_test([1], [2])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_significance_zero_variance_handled():
    result = paired_significance_test([5.0, 4.0, 6.0], [6.0, 5.0, 7.0])
    assert result["significant"] is True
    assert result["mean_difference"] == -1.0


# ---------- compare.py CLI ----------

def test_compare_cli_missing_file(tmp_path):
    result = subprocess.run(
        [sys.executable, "compare.py", "--results", "does_not_exist.json"],
        capture_output=True, text=True, cwd=EVAL_FRAMEWORK_DIR
    )
    assert result.returncode != 0
    assert "Error loading" in result.stdout


def test_compare_cli_bad_json(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ this is not valid json")
    result = subprocess.run(
        [sys.executable, "compare.py", "--results", str(bad_file)],
        capture_output=True, text=True, cwd=EVAL_FRAMEWORK_DIR
    )
    assert result.returncode != 0
    assert "Error loading" in result.stdout


def test_compare_cli_empty_json(tmp_path):
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("{}")
    result = subprocess.run(
        [sys.executable, "compare.py", "--results", str(empty_file)],
        capture_output=True, text=True, cwd=EVAL_FRAMEWORK_DIR
    )
    assert result.returncode != 0
    assert "non-empty" in result.stdout


def test_compare_cli_mismatched_metrics(tmp_path):
    mismatched_file = tmp_path / "mismatched.json"
    mismatched_file.write_text(json.dumps({
        "naive": {"mape": 6.80, "rmse": 39955.47},
        "prophet": {"mape": 3.20}
    }))
    result = subprocess.run(
        [sys.executable, "compare.py", "--results", str(mismatched_file)],
        capture_output=True, text=True, cwd=EVAL_FRAMEWORK_DIR
    )
    assert result.returncode == 0
    assert "N/A" in result.stdout
    assert "mape" in result.stdout


# ---------- guardrails.py ----------

def test_guardrail_clean_split_passes():
    train = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=5), "y": range(5)})
    test = pd.DataFrame({"date": pd.date_range("2024-01-06", periods=2), "y": range(5, 7)})
    check_no_train_test_overlap(train, test)
    check_chronological_order(train, test, "date")


def test_guardrail_catches_overlap():
    train = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=5), "y": range(5)})
    leaky_test = pd.DataFrame({"date": [train["date"].iloc[0]], "y": [0]})
    try:
        check_no_train_test_overlap(train, leaky_test)
        assert False, "expected LeakageError"
    except LeakageError:
        pass


def test_guardrail_catches_chronological_violation():
    train = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=10)})
    bad_test = pd.DataFrame({"date": pd.date_range("2024-01-05", periods=3)})
    try:
        check_chronological_order(train, bad_test, "date")
        assert False, "expected LeakageError"
    except LeakageError:
        pass


def test_guardrail_flags_suspicious_accuracy():
    warnings = check_suspicious_accuracy(0.999)
    assert len(warnings) == 1
    assert "leakage" in warnings[0].lower()


def test_guardrail_does_not_flag_normal_accuracy():
    warnings = check_suspicious_accuracy(0.75)
    assert warnings == []


def test_run_all_guardrails_clean_case():
    train = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=5), "y": range(5)})
    test = pd.DataFrame({"date": pd.date_range("2024-01-06", periods=2), "y": range(5, 7)})
    result = run_all_guardrails(train, test, "date", score=0.75)
    assert result["passed"] is True
    assert result["warnings"] == []


def test_run_all_guardrails_raises_on_leakage():
    train = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=5), "y": range(5)})
    leaky_test = pd.DataFrame({"date": [train["date"].iloc[0]], "y": [0]})
    try:
        run_all_guardrails(train, leaky_test, "date")
        assert False, "expected LeakageError"
    except LeakageError:
        pass


# ---------- backtest.py ----------

def _naive_forecast_fn(train_df, horizon):
    last_value = train_df["y"].iloc[-1]
    return [last_value] * horizon


def test_backtest_basic():
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=30), "y": list(range(30))})
    results = backtest(df, "date", "y", _naive_forecast_fn, horizon=1, min_train_size=10)
    assert len(results) == 20
    assert results[0]["actual"] == [10]
    assert results[-1]["actual"] == [29]


def test_backtest_respects_min_train_size():
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=30), "y": list(range(30))})
    results = backtest(df, "date", "y", _naive_forecast_fn, horizon=1, min_train_size=25)
    assert len(results) == 5


def test_backtest_multi_step_horizon():
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=30), "y": list(range(30))})
    results = backtest(df, "date", "y", _naive_forecast_fn, horizon=3, min_train_size=10)
    assert len(results[0]["actual"]) == 3
    assert len(results[0]["predicted"]) == 3


def test_backtest_step_parameter_reduces_window_count():
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=30), "y": list(range(30))})
    dense = backtest(df, "date", "y", _naive_forecast_fn, horizon=1, min_train_size=10, step=1)
    sparse = backtest(df, "date", "y", _naive_forecast_fn, horizon=1, min_train_size=10, step=2)
    assert len(sparse) < len(dense)


def test_backtest_insufficient_data_raises():
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=5), "y": list(range(5))})
    try:
        backtest(df, "date", "y", _naive_forecast_fn, horizon=1, min_train_size=10)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_backtest_integrates_with_mape():
    from src.metrics import mape as _mape
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=30), "y": list(range(30))})
    results = backtest(df, "date", "y", _naive_forecast_fn, horizon=1, min_train_size=10)
    all_actual = [r["actual"][0] for r in results]
    all_predicted = [r["predicted"][0] for r in results]
    score = _mape(all_actual, all_predicted)
    assert score > 0

# ---------- report_html.py ----------
def test_html_report_contains_model_names():
    results = {"naive": {"mape": 6.22}, "prophet": {"mape": 8.78}}
    html = generate_html_report(results, title="Test Report")
    assert "naive" in html
    assert "prophet" in html
    assert "Test Report" in html


def test_html_report_contains_metric_values():
    results = {"naive": {"mape": 6.22}, "prophet": {"mape": 8.78}}
    html = generate_html_report(results)
    assert "6.2200" in html
    assert "8.7800" in html


def test_html_report_includes_significance_when_provided():
    results = {"naive": {"mape": 6.22}, "prophet": {"mape": 8.78}}
    sig_result = {"interpretation": "This is a test interpretation string."}
    html = generate_html_report(results, significance_result=sig_result)
    assert "This is a test interpretation string." in html


def test_html_report_omits_significance_when_not_provided():
    results = {"naive": {"mape": 6.22}, "prophet": {"mape": 8.78}}
    html = generate_html_report(results)
    assert "Statistical Significance" not in html


def test_html_report_includes_chart_images():
    results = {"naive": {"mape": 6.22}, "prophet": {"mape": 8.78}}
    html = generate_html_report(results)
    assert "data:image/png;base64," in html


def test_save_html_report_writes_file(tmp_path):
    results = {"naive": {"mape": 6.22}, "prophet": {"mape": 8.78}}
    output_path = tmp_path / "test_report.html"
    save_html_report(results, str(output_path))
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "naive" in content

def test_leaderboard_service_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_leaderboard_service_ranks_correctly():
    response = client.post("/leaderboard", json={
        "results": {"naive": {"mape": 6.80}, "prophet": {"mape": 3.20}},
        "metric": "mape"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["leaderboard"][0]["model"] == "prophet"
    assert data["leaderboard"][0]["rank"] == 1


def test_leaderboard_service_refuses_incompatible_metrics():
    response = client.post("/leaderboard", json={
        "results": {"naive": {"mape": 6.80}, "xgboost": {"precision": 0.9}},
        "metric": "mape"
    })
    assert response.status_code == 422
    assert "xgboost" in response.json()["detail"]


def test_leaderboard_service_rejects_malformed_request():
    response = client.post("/leaderboard", json={"results": "not a dict"})
    assert response.status_code == 422