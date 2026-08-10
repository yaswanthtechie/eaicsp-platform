import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.metrics import mape, rmse
from src.baseline import naive_forecast, compare_to_baseline
from src.splits import time_based_split
import pandas as pd


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