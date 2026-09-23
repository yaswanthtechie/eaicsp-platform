import math

import pandas as pd

from .metrics import KNOWN_METRICS, HIGHER_IS_BETTER_METRICS


def detect_regression(runs_df: pd.DataFrame, owner: str, model_name: str, metric: str,
                         lower_is_better: bool = None, owner_tag_col: str = "tags.owner",
                         model_tag_col: str = "tags.model_name",
                         degradation_threshold: float = 0.0) -> dict:
    """
    Compares a model's two most recent logged runs and flags whether the
    latest run is WORSE than the one before it.

    metric: must be a KNOWN_METRICS name, or lower_is_better must be given
        explicitly.
    degradation_threshold: fraction worse the new run must be before it's
        flagged. Scores that are numerically indistinguishable (within
        floating-point tolerance) are NEVER flagged as a regression,
        regardless of threshold -- otherwise trivial floating-point noise
        between two runs of an unchanged model would falsely trigger a
        regression alert (the same class of instability guarded against in
        significance.py's zero-variance case).

    Returns:
    {
        "regressed": bool,
        "previous_score": float,
        "latest_score": float,
        "previous_run_id": str,
        "latest_run_id": str,
        "message": str,
    }

    Raises ValueError if fewer than 2 runs exist for this owner/model, or
    if the metric is unrecognized with no explicit direction.
    """
    metric_key = metric.lower()
    is_known = metric_key in KNOWN_METRICS
    if not is_known and lower_is_better is None:
        raise ValueError(
            f"detect_regression: '{metric}' is not a recognized metric, and "
            f"no lower_is_better direction was given. Known metrics: "
            f"{sorted(KNOWN_METRICS)}."
        )
    if lower_is_better is None:
        lower_is_better = metric_key not in HIGHER_IS_BETTER_METRICS

    metric_col = f"metrics.{metric}"
    if metric_col not in runs_df.columns:
        raise ValueError(f"detect_regression: metric column '{metric_col}' not found.")

    subset = runs_df[
        (runs_df[owner_tag_col] == owner) & (runs_df[model_tag_col] == model_name)
    ].sort_values("start_time", ascending=False)

    if len(subset) < 2:
        raise ValueError(
            f"detect_regression: need at least 2 runs for owner='{owner}', "
            f"model='{model_name}' to compare -- found {len(subset)}."
        )

    latest = subset.iloc[0]
    previous = subset.iloc[1]
    latest_score = latest[metric_col]
    previous_score = previous[metric_col]

    if math.isclose(latest_score, previous_score, rel_tol=1e-9, abs_tol=1e-9):
        regressed = False
    elif lower_is_better:
        regressed = bool(latest_score > previous_score * (1 + degradation_threshold))
    else:
        regressed = bool(latest_score < previous_score * (1 - degradation_threshold))
    message = (
        f"REGRESSION DETECTED: {model_name} ({owner})'s latest {metric} "
        f"({latest_score:.4f}) is worse than the previous run "
        f"({previous_score:.4f})."
        if regressed else
        f"No regression: {model_name} ({owner})'s latest {metric} "
        f"({latest_score:.4f}) is not worse than the previous run "
        f"({previous_score:.4f})."
    )

    return {
        "regressed": regressed,
        "previous_score": previous_score,
        "latest_score": latest_score,
        "previous_run_id": previous["run_id"],
        "latest_run_id": latest["run_id"],
        "message": message,
    }