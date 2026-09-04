import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.metrics import mape, rmse
from src.baseline import naive_forecast, compare_to_baseline
from src.splits import time_based_split
import pandas as pd
from src.metrics import confusion_matrix, precision_recall
from src.splits import walk_forward_split
import json
import subprocess
import sys
from src.metrics import anomaly_metrics
from src.leaderboard import generate_leaderboard, print_leaderboard
from src.significance import paired_significance_test
EVAL_FRAMEWORK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))




def test_mape():
    assert round(mape([100, 200], [110, 190]), 2) == 7.5


def test_rmse():
    assert round(rmse([100, 200], [110, 190]), 2) == 10.0


def test_naive_forecast():
    assert naive_forecast([10, 20, 30, 40]) == [10, 10, 20, 30]


def test_compare_to_baseline():
    result = compare_to_baseline([100, 200], [110, 190], [100, 200])
    assert result["mape_winner"] == "model"


def test_time_based_split_no_leakage():
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=10), "y": range(10)})
    train, test = time_based_split(df, "date", test_size=0.2)
    assert len(train) == 8 and len(test) == 2
    assert train["date"].max() < test["date"].min()
    
def test_compare_to_baseline_tie():
    result = compare_to_baseline([110, 190], [110, 190], [100, 200])
    assert result["mape_winner"] == "tie"
    assert result["mape_diff"] == 0
    assert result["rmse_winner"] == "tie"
    assert result["rmse_diff"] == 0



def test_confusion_matrix_basic():
    result = confusion_matrix([1, 0, 1, 0], [1, 0, 0, 0])
    assert result == {"tp": 1, "tn": 2, "fp": 0, "fn": 1}


def test_confusion_matrix_empty_raises():
    try:
        confusion_matrix([], [])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_precision_recall_all_same_class():
    # every prediction is 0, no actual positives predicted correctly
    result = precision_recall([1, 1, 0], [0, 0, 0])
    assert result["precision"] == 0.0
    assert result["recall"] == 0.0
    assert result["f1"] == 0.0


def test_precision_recall_perfect():
    result = precision_recall([1, 0, 1, 0], [1, 0, 1, 0])
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["f1"] == 1.0


def test_walk_forward_split_basic():
    import pandas as pd
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=20), "y": range(20)})
    folds = walk_forward_split(df, "date", n_splits=3)
    assert len(folds) == 3
    for train, test in folds:
        assert train["date"].max() < test["date"].min()


def test_walk_forward_split_too_little_data_raises():
    import pandas as pd
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=1), "y": [1]})
    try:
        walk_forward_split(df, "date", n_splits=3)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_mape_single_row():
    assert round(mape([100], [110]), 2) == 10.0

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


def test_anomaly_metrics_basic():
    y_true = [0,0,0,1,0,0,0,1,0,0]
    y_pred = [0,0,0,1,0,0,1,0,0,0]
    result = anomaly_metrics(y_true, y_pred)
    assert result["recall"] == 0.5
    assert result["specificity"] == 0.875
    assert round(result["false_positive_rate"], 3) == 0.125
    assert round(result["balanced_accuracy"], 4) == 0.6875



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


def test_leaderboard_rejects_non_numeric_value():
    try:
        generate_leaderboard({"a": {"mape": "high"}, "b": {"mape": 3.2}}, "mape")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "a" in str(e)

def test_anomaly_metrics_all_normal():
    # No anomalies exist at all, and none predicted -- recall is trivially 0
    # (nothing to catch), specificity should be perfect (correctly left everything alone)
    y_true = [0, 0, 0, 0, 0]
    y_pred = [0, 0, 0, 0, 0]
    result = anomaly_metrics(y_true, y_pred)
    assert result["recall"] == 0.0
    assert result["specificity"] == 1.0
    assert result["false_positive_rate"] == 0.0
    assert result["balanced_accuracy"] == 0.5


def test_anomaly_metrics_all_anomaly():
    # Every point is a real anomaly, all correctly caught
    y_true = [1, 1, 1, 1]
    y_pred = [1, 1, 1, 1]
    result = anomaly_metrics(y_true, y_pred)
    assert result["recall"] == 1.0
    # No normal points exist, so specificity's denominator (tn+fp) is 0 -> defaults to 0.0
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
    # {-1, 1} is the sklearn IsolationForest/LOF convention -- must raise,
    # not silently miscount
    try:
        anomaly_metrics([1, -1, 1, -1], [1, 1, -1, -1])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "-1" in str(e) or "unexpected value" in str(e)


def test_confusion_matrix_rejects_sklearn_style_labels():
    try:
        confusion_matrix([1, -1], [1, -1])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "0 or 1" in str(e)

def test_leaderboard_rejects_nan():
    try:
        generate_leaderboard({"a": {"mape": float("nan")}, "b": {"mape": 3.2}}, "mape")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "a" in str(e)