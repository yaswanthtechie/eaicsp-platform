import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error



import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_true = np.asarray(y_true, dtype=float).reshape(-1)
    y_pred = np.asarray(y_pred, dtype=float).reshape(-1)

    if y_true.shape != y_pred.shape:
        raise ValueError(
            f"Shape mismatch: y_true={y_true.shape}, y_pred={y_pred.shape}"
        )

    if y_true.size == 0:
        raise ValueError("Cannot calculate metrics for empty arrays")

    if not np.all(np.isfinite(y_true)) or not np.all(np.isfinite(y_pred)):
        raise ValueError("y_true and y_pred must contain only finite values")

    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))

    # MAPE is defined only for non-zero actual values.
    nonzero_mask = y_true != 0
    if np.any(nonzero_mask):
        mape = np.mean(
            np.abs(
                (y_true[nonzero_mask] - y_pred[nonzero_mask])
                / y_true[nonzero_mask]
            )
        ) * 100.0
        mape_value = float(mape)
    else:
        mape_value = None

    return {
        "MAE": float(mae),
        "RMSE": float(rmse),
        "MAPE": mape_value,
    }


def predict_naive_baseline(
    X_test: np.ndarray, horizon: int = 7
) -> np.ndarray:
    """
    Repeat the last observed value across the forecast horizon.

    Supports 2D input (N, L) and 3D input (N, L, 1).
    """
    X_test = np.asarray(X_test)

    if X_test.ndim not in (2, 3):
        raise ValueError(
            f"Expected 2D or 3D input, got {X_test.ndim}D"
        )

    if X_test.shape[1] == 0:
        raise ValueError("Lookback window cannot be empty")

    if X_test.ndim == 3:
        if X_test.shape[2] != 1:
            raise ValueError("3D input must have a single feature")
        last_val = X_test[:, -1, 0]
    else:
        last_val = X_test[:, -1]

    if horizon < 1:
        raise ValueError("horizon must be >= 1")

    return np.repeat(last_val[:, np.newaxis], horizon, axis=1)
