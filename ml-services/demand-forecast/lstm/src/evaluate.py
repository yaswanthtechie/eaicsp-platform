import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_true = np.asarray(y_true).reshape(-1)
    y_pred = np.asarray(y_pred).reshape(-1)
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mape = np.mean(np.abs((y_true - y_pred) / np.clip(np.abs(y_true), 1e-8, None))) * 100
    return {"MAE": float(mae), "RMSE": float(rmse), "MAPE": float(mape)}


def predict_naive_baseline(X_test: np.ndarray, horizon: int = 7) -> np.ndarray:
    """
    Predicts the last observed value from the lookback window repeated across the horizon.
    Handles both 2D (N, L) and 3D (N, L, 1) input arrays safely.
    """
    if X_test.ndim == 3:
        last_val = X_test[:, -1, :].squeeze(-1)
    else:
        last_val = X_test[:, -1]
    
    # Broadcast (N, 1) -> (N, horizon)
    return np.tile(last_val[:, np.newaxis], (1, horizon))