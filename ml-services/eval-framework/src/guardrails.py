import pandas as pd


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


def check_suspicious_accuracy(score: float, metric_name: str = "accuracy",
                                 threshold: float = 0.98) -> list:
    """Flags (does not raise) if a score is suspiciously high -- often a
    sign of data leakage rather than genuine model skill, especially for
    real-world noisy data where near-perfect scores are rare.

    Returns a list of warning strings (empty list if nothing suspicious).
    This is a soft warning, not a hard failure, since some problems
    genuinely can be solved near-perfectly (e.g. a trivial classification
    task) -- the caller decides whether to treat it as blocking.
    """
    warnings = []
    if score >= threshold:
        warnings.append(
            f"Suspicious result: {metric_name}={score:.4f} is at or above the "
            f"{threshold} threshold. Real-world results this high often indicate "
            f"data leakage (e.g. a feature that indirectly encodes the target, "
            f"or train/test overlap) rather than genuine model skill. Worth "
            f"double-checking before trusting this number."
        )
    return warnings


def check_chronological_order(train: pd.DataFrame, test: pd.DataFrame, date_col: str) -> None:
    """Hard-fails if any test date is earlier than or equal to the latest
    train date -- enforces the project's core rule that training data must
    always come strictly before test data in time.
    """
    train_max = train[date_col].max()
    test_min = test[date_col].min()
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