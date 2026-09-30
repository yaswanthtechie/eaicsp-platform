import pandas as pd

from .metrics import HIGHER_IS_BETTER_METRICS, KNOWN_METRICS, SUSPICIOUS_THRESHOLDS


class LeakageError(Exception):
    """Raised when a guardrail detects a hard failure -- something that
    must never happen, like train/test overlap. Distinct from ValueError
    so callers can specifically catch data-integrity failures.
    """
    pass


def check_no_train_test_overlap(train: pd.DataFrame, test: pd.DataFrame, on: list = None) -> None:
    """Hard-fails if any row appears in both train and test.

    on: optional list of column names to check for overlap (e.g. an ID
    column). If not given, checks for fully identical rows across all
    shared columns -- a stricter, catch-all check.

    Raises LeakageError if any overlap is found. Returns None (silently
    passes) if the split is clean.
    """
    if on:
        train_keys = set(map(tuple, train[on].values))
        test_keys = set(map(tuple, test[on].values))
    else:
        shared_cols = [c for c in train.columns if c in test.columns]
        train_keys = set(map(tuple, train[shared_cols].values))
        test_keys = set(map(tuple, test[shared_cols].values))

    overlap = train_keys & test_keys
    if overlap:
        raise LeakageError(
            f"Train/test overlap detected: {len(overlap)} row(s) appear in both sets. "
            f"This is a hard failure -- a model trained and tested on the same data "
            f"will report falsely inflated performance."
        )


def check_suspicious_accuracy(score: float, metric_name: str = "accuracy") -> list:
    """Flags (does not raise) if a score is suspiciously good -- often a
    sign of data leakage rather than genuine model skill.

    Metric name matching is case-insensitive (so "Accuracy" and "accuracy"
    both work). Thresholds are looked up per-metric from
    SUSPICIOUS_THRESHOLDS in metrics.py, since different metrics live on
    very different scales (MAPE is a percentage 0-100, accuracy is a
    fraction 0-1 -- one shared threshold cannot correctly apply to both).

    If metric_name is not a recognized metric (not in KNOWN_METRICS), this
    returns an explicit warning saying the metric is unrecognized and the
    check was skipped -- NOT a silent guess at direction. Silently
    defaulting unknown metrics to "lower is better" previously caused
    real bugs: r2 ranked backwards, and auc / false_positive_rate flagged
    incorrectly.

    Returns a list of warning strings (empty list if nothing suspicious).
    This is a soft warning, not a hard failure -- the caller decides
    whether to treat any warning as blocking.
    """
    metric_key = metric_name.lower()

    if metric_key not in KNOWN_METRICS:
        return [
            f"Metric '{metric_name}' is not recognized by this framework -- cannot "
            f"determine whether a high or low value is suspicious, so this check "
            f"was skipped. Known metrics: {sorted(KNOWN_METRICS)}."
        ]

    is_higher_better = metric_key in HIGHER_IS_BETTER_METRICS
    thresholds = SUSPICIOUS_THRESHOLDS.get(metric_key, {})
    warnings = []

    if is_higher_better and "high" in thresholds:
        threshold = thresholds["high"]
        if score >= threshold:
            warnings.append(
                f"Suspicious result: {metric_name}={score:.4f} is at or above the "
                f"{threshold} threshold. Real-world results this high often indicate "
                f"data leakage (e.g. a feature that indirectly encodes the target, "
                f"or train/test overlap) rather than genuine model skill. Worth "
                f"double-checking before trusting this number."
            )
    elif not is_higher_better and "low" in thresholds:
        threshold = thresholds["low"]
        if score <= threshold:
            warnings.append(
                f"Suspicious result: {metric_name}={score:.4f} is at or below the "
                f"{threshold} threshold. For a lower-is-better metric like this "
                f"(e.g. MAPE, RMSE), a near-zero error is the same red flag as a "
                f"near-perfect accuracy elsewhere -- often data leakage rather than "
                f"genuine model skill. Worth double-checking before trusting this number."
            )

    return warnings


def check_chronological_order(train: pd.DataFrame, test: pd.DataFrame, date_col: str,
                                 dayfirst: bool = False, date_format: str = None) -> None:
    """Hard-fails if any test date is earlier than or equal to the latest
    train date -- enforces the project's core rule that training data must
    always come strictly before test data in time.

    Dates are explicitly converted with pd.to_datetime before comparing --
    comparing raw strings can both false-alarm on clean splits and, worse,
    silently miss real leaks.

    dayfirst / date_format: passed through to pd.to_datetime, since date
    strings are genuinely ambiguous (e.g. "10/01/2024" could be Jan 10 or
    Oct 1) -- pass whichever matches your data's actual convention.

    Raises ValueError (not LeakageError) if either dataframe is empty --
    that's a usage error, not a leakage finding, so it gets a clear message
    instead of a raw crash.
    """
    if len(train) == 0 or len(test) == 0:
        raise ValueError(
            "check_chronological_order: train and test must both be non-empty."
        )

    train_dates = pd.to_datetime(train[date_col], dayfirst=dayfirst, format=date_format)
    test_dates = pd.to_datetime(test[date_col], dayfirst=dayfirst, format=date_format)

    train_max = train_dates.max()
    test_min = test_dates.min()

    if test_min <= train_max:
        raise LeakageError(
            f"Chronological order violated: latest train date ({train_max}) is "
            f"not strictly before earliest test date ({test_min}). This means "
            f"the model could have trained on data from the same time as, or "
            f"after, what it's being tested on -- a hard failure."
        )


def run_all_guardrails(train: pd.DataFrame, test: pd.DataFrame, date_col: str,
                          score: float = None, metric_name: str = "accuracy") -> dict:
    """Convenience function: runs every guardrail check in one call.
    Hard failures (LeakageError) propagate immediately. Soft warnings are
    collected and returned.

    Returns {"passed": bool, "warnings": [str, ...]}.
    """
    check_no_train_test_overlap(train, test)
    check_chronological_order(train, test, date_col)

    warnings = []
    if score is not None:
        warnings = check_suspicious_accuracy(score, metric_name)

    return {"passed": True, "warnings": warnings}