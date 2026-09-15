import numpy as np
# Metrics where a HIGHER value is better. Every other known metric (mape, rmse,
# false_positive_rate, etc.) is treated as lower-is-better by default. This is
# the single source of truth used by both report.py and leaderboard.py, so
# adding a new metric here automatically fixes its winner-direction everywhere.
HIGHER_IS_BETTER_METRICS = {"precision", "recall", "f1", "balanced_accuracy", "specificity"}


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
    """Returns {tp, tn, fp, fn} for binary classification.
    Requires labels to be exactly 0 (normal/negative) or 1 (anomaly/positive).
    Common sklearn anomaly detectors (IsolationForest, LOF) output {-1, 1}
    instead -- remap those to {0, 1} before calling this, or this function
    will raise a clear error rather than silently miscounting.
    """
    y_true, y_pred = list(y_true), list(y_pred)
    if len(y_true) == 0 or len(y_pred) == 0:
        raise ValueError("confusion_matrix: y_true and y_pred must not be empty")
    if len(y_true) != len(y_pred):
        raise ValueError("confusion_matrix: y_true and y_pred must be the same length")

    valid_labels = {0, 1}
    invalid = [v for v in set(y_true) | set(y_pred) if v not in valid_labels]
    if invalid:
        raise ValueError(
            f"confusion_matrix: labels must be 0 or 1, got unexpected value(s) {invalid}. "
            f"If using sklearn-style anomaly labels ({{-1, 1}}), remap with "
            f"e.g. [0 if v == 1 else 1 for v in labels] (1=normal->0, -1=anomaly->1) "
            f"before calling this function."
        )

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


def anomaly_metrics(y_true, y_pred) -> dict:
    """Anomaly-detection specific metrics, built on top of confusion_matrix.
    Includes false positive rate and balanced accuracy -- both matter more than
    plain precision/recall when anomalies are rare compared to normal points
    (severe class imbalance), which is the typical real-world anomaly setting.
    """
    cm = confusion_matrix(y_true, y_pred)
    tp, tn, fp, fn = cm["tp"], cm["tn"], cm["fp"], cm["fn"]

    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    balanced_accuracy = (recall + specificity) / 2

    return {
        "recall": recall,
        "specificity": specificity,
        "false_positive_rate": fpr,
        "balanced_accuracy": balanced_accuracy,
    }