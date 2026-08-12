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


def confusion_matrix(y_true, y_pred) -> dict:
    """Returns {tp, tn, fp, fn} for binary classification (labels 0/1 or False/True).
    Raises ValueError on empty input rather than crashing with a confusing numpy error.
    """
    y_true, y_pred = list(y_true), list(y_pred)
    if len(y_true) == 0 or len(y_pred) == 0:
        raise ValueError("confusion_matrix: y_true and y_pred must not be empty")
    if len(y_true) != len(y_pred):
        raise ValueError("confusion_matrix: y_true and y_pred must be the same length")

    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    return {"tp": tp, "tn": tn, "fp": fp, "fn": fn}


def precision_recall(y_true, y_pred) -> dict:
    """For classification/anomaly models: {precision, recall, f1}.
    Handles edge cases explicitly instead of crashing or silently returning 0:
    - empty input -> raises ValueError
    - no predicted positives (all-same-class predictions where predicted=0) -> precision=0.0
    - no actual positives -> recall=0.0
    """
    cm = confusion_matrix(y_true, y_pred)
    tp, fp, fn = cm["tp"], cm["fp"], cm["fn"]

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1}