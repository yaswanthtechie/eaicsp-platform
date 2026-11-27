import numpy as np

from src.walk_forward_comparison import safe_metrics


def test_safe_metrics_returns_none_for_empty_input():
    assert safe_metrics(np.array([]), np.array([])) == {
        "MAE": None,
        "RMSE": None,
        "MAPE": None,
    }
    assert safe_metrics(np.array([1.0, 2.0]), np.array([1.0, 2.0]))["MAE"] == 0.0
