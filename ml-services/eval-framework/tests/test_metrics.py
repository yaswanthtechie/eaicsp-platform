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
        capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "Error loading" in result.stdout


def test_compare_cli_bad_json(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ this is not valid json")
    result = subprocess.run(
        [sys.executable, "compare.py", "--results", str(bad_file)],
        capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "Error loading" in result.stdout


def test_compare_cli_empty_json(tmp_path):
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("{}")
    result = subprocess.run(
        [sys.executable, "compare.py", "--results", str(empty_file)],
        capture_output=True, text=True
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
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "N/A" in result.stdout
    assert "mape" in result.stdout