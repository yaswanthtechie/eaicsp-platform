"""Anomaly-detection evaluation: threshold metrics, PR-AUC, precision@k, events."""
import numpy as np

from ._validation import check_same_length, to_binary_array, to_float_array
from .metrics import precision_recall


def threshold_metrics(y_true, scores, threshold) -> dict:
    """Precision/recall/F1 after flagging every point with score >= threshold.

    Why: detectors output scores, and P/R/F1 only exist at a chosen threshold.
    The threshold is a required argument so nobody reports "the" F1 of a
    detector without stating where it was cut. Undefined ratios follow
    precision_recall(): 0.0 when nothing is flagged / nothing is positive.
    """
    y = to_binary_array(y_true, "y_true")
    s = to_float_array(scores, "scores")
    check_same_length(y_true=y, scores=s)
    try:
        thr = float(threshold)
    except (TypeError, ValueError) as exc:
        raise ValueError("threshold must be a finite number") from exc
    if not np.isfinite(thr):
        raise ValueError("threshold must be a finite number")
    y_pred = (s >= thr).astype(int)
    result = precision_recall(y, y_pred)
    result["threshold"] = thr
    result["n_flagged"] = int(y_pred.sum())
    return result


def pr_auc(y_true, scores) -> float:
    """Area under the precision-recall curve (average precision, step-wise).

    Why: anomalies are rare, so ROC-AUC looks flattering; PR-AUC does not and
    needs no threshold. Tied scores are grouped into a single threshold so the
    result does not depend on row order. Raises if there are no positives,
    because recall is undefined then (a fabricated 0 or 1 would mislead).
    """
    y = to_binary_array(y_true, "y_true")
    s = to_float_array(scores, "scores")
    check_same_length(y_true=y, scores=s)
    n_pos = int(y.sum())
    if n_pos == 0:
        raise ValueError("pr_auc undefined: y_true has no positive labels")

    order = np.argsort(-s, kind="stable")
    s, y = s[order], y[order]
    tps = np.cumsum(y)
    fps = np.cumsum(1 - y)
    last_of_group = np.r_[np.where(np.diff(s) != 0)[0], len(s) - 1]
    tp, fp = tps[last_of_group], fps[last_of_group]
    precision = tp / (tp + fp)
    recall = tp / n_pos
    prev_recall = np.r_[0.0, recall[:-1]]
    return float(np.sum((recall - prev_recall) * precision))


def precision_at_k(y_true, scores, k, on_tie: str = "raise") -> float:
    """Fraction of true anomalies among the k highest-scored points.

    Why: an on-call engineer can only review the top k alerts, so this is the
    metric that matches real usage. If tied scores straddle the k-th boundary
    the top-k set is ambiguous; by default we raise rather than pick silently.
    Pass on_tie="first" to accept earliest-index-first ordering explicitly.
    """
    if on_tie not in ("raise", "first"):
        raise ValueError("on_tie must be 'raise' or 'first'")
    y = to_binary_array(y_true, "y_true")
    s = to_float_array(scores, "scores")
    check_same_length(y_true=y, scores=s)
    n = len(y)
    if isinstance(k, bool) or not isinstance(k, (int, np.integer)) or k < 1 or k > n:
        raise ValueError(f"k must be an integer between 1 and {n}, got {k!r}")

    order = np.argsort(-s, kind="stable")
    if on_tie == "raise" and k < n and s[order[k - 1]] == s[order[k]]:
        raise ValueError(
            "precision_at_k: tied scores straddle the k-th position, so the "
            "top-k set is ambiguous. Pass on_tie='first' to accept index order."
        )
    return float(y[order[:k]].sum() / k)


def find_events(labels) -> list:
    """Return [(start, end), ...] (inclusive indices) for each run of 1s.

    Why: one outage lasting 10 steps is ONE event; grouping consecutive
    positives is the basis of event-level scoring. Input must be in
    chronological order with evenly spaced steps.
    """
    arr = to_binary_array(labels, "labels")
    d = np.diff(np.concatenate(([0], arr, [0])))
    starts = np.where(d == 1)[0]
    ends = np.where(d == -1)[0] - 1
    return list(zip(starts.tolist(), ends.tolist()))


def event_scores(y_true, y_pred, tolerance: int = 0) -> dict:
    """Event-level precision/recall/F1.

    Why: point-level metrics reward long overlap and punish early detection.
    Here a true event is 'detected' if any predicted run overlaps it (widened
    by `tolerance` steps on each side); a predicted run overlapping no true
    event is one false-alarm event. Undefined ratios (no predicted events, or
    no true events) are returned as None, never a fabricated 0.
    """
    yt = to_binary_array(y_true, "y_true")
    yp = to_binary_array(y_pred, "y_pred")
    check_same_length(y_true=yt, y_pred=yp)
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, np.integer)) or tolerance < 0:
        raise ValueError("tolerance must be a non-negative integer (time steps)")

    true_events = find_events(yt)
    pred_events = find_events(yp)

    def overlaps(pred, true):
        return pred[0] <= true[1] + tolerance and pred[1] >= true[0] - tolerance

    detected = sum(1 for t in true_events if any(overlaps(p, t) for p in pred_events))
    matched_pred = sum(1 for p in pred_events if any(overlaps(p, t) for t in true_events))

    precision = matched_pred / len(pred_events) if pred_events else None
    recall = detected / len(true_events) if true_events else None
    if precision is None or recall is None:
        f1 = None
    elif precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return {
        "event_precision": precision,
        "event_recall": recall,
        "event_f1": f1,
        "n_true_events": len(true_events),
        "n_pred_events": len(pred_events),
        "events_detected": detected,
        "false_alarm_events": len(pred_events) - matched_pred,
    }