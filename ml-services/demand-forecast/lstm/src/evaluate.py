"""
Evaluation Metrics & Baseline Calculations
-------------------------------------------------------
Computes MAE, RMSE, MAPE, and calculates the Naive Persistence Baseline.
"""

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Computes MAE, RMSE, and MAPE metrics."""
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mape = np.mean(np.abs((y_true - y_pred) / (y_true + 1e-8))) * 100
    return {"MAE": float(mae), "RMSE": float(rmse), "MAPE": float(mape)}


def predict_naive_baseline(X_test: np.ndarray, horizon: int = 7) -> np.ndarray:
    """
    Naive Baseline Strategy: y_{t+h} = y_t (Tomorrow = Today).
    Repeats the last observed value from lookback window across the 7-day horizon.
    """
    last_observed_value = X_test[:, -1]  # Take last observed timestep from lookback
    y_pred_naive = np.tile(last_observed_value[:, np.newaxis], (1, horizon))
    return y_pred_naive