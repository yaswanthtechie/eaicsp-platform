import numpy as np


def mape(actual, predicted) -> float:
    """Mean Absolute Percentage Error, standard for forecasting.
    Rows where actual == 0 are excluded, since percentage error is undefined there.
    """
    actual, predicted = np.array(actual), np.array(predicted)
    mask = actual != 0
    if not mask.any():
        raise ValueError("MAPE undefined: all actual values are zero")
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def rmse(actual, predicted) -> float:
    """Root Mean Squared Error."""
    actual, predicted = np.array(actual), np.array(predicted)
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def precision_recall(y_true, y_pred) -> dict:
    """For classification/anomaly models: {precision, recall, f1}"""
    from sklearn.metrics import precision_score, recall_score, f1_score
    return {
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
    }