import math

import pandas as pd

from .metrics import KNOWN_METRICS, HIGHER_IS_BETTER_METRICS


def detect_regression(runs_df: pd.DataFrame, owner: str, model_name: str, metric: str,
                         lower_is_better: bool = None, owner_tag_col: str = "tags.owner",
                         model_tag_col: str = "tags.model_name",
                         degradation_threshold: float = 0.0,
                         baseline: str = "previous", stage_tag_col: str = "tags.stage") -> dict:
    """
    Compares a model's latest logged run against a baseline run and flags
    whether the latest is WORSE.

    baseline: "previous" (default) compares against the immediately prior
        logged run by timestamp -- note this compares consecutive runs,
        not necessarily "this week vs last week"; several runs logged in
        one afternoon are compared to each other, not to what's actually
        deployed. Use baseline="production" to compare against the most
        recent run tagged {stage_tag_col}="production" instead, which
        compares a new retrain against what's actually shipped.

    metric: must be a KNOWN_METRICS name, or lower_is_better must be given
        explicitly.

    degradation_threshold: fraction worse the new run must be, measured as
        a fraction of the baseline's absolute magnitude (abs(previous_score)
        * degradation_threshold) -- using the absolute value specifically
        so this works correctly for metrics that can be negative (a naive
        multiplicative threshold on a negative score flips comparison
        direction and silently breaks).

    A run missing the metric being compared (NaN) is a hard failure, not
    "no regression" -- silently treating a broken/incomplete run as
    equivalent to "no regression" is a worse failure mode than raising,
    since it would hide the fact that something didn't get measured at all.

    Returns:
    {
        "regressed": bool,
        "previous_score": float,
        "latest_score": float,
        "previous_run_id": str,
        "latest_run_id": str,
        "baseline": str,
        "message": str,
    }

    Raises ValueError if fewer than 2 runs exist, the metric is unrecognized
    with no explicit direction, either compared run is missing the metric,
    baseline="production" is requested but no production-tagged run exists,
    or baseline is neither "previous" nor "production".
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

    if baseline not in ("previous", "production"):
        raise ValueError(f"detect_regression: baseline must be 'previous' or 'production', got '{baseline}'.")

    subset = runs_df[
        (runs_df[owner_tag_col] == owner) & (runs_df[model_tag_col] == model_name)
    ].sort_values("start_time", ascending=False)

    if len(subset) < 2:
        raise ValueError(
            f"detect_regression: need at least 2 runs for owner='{owner}', "
            f"model='{model_name}' to compare -- found {len(subset)}."
        )

    latest = subset.iloc[0]

    if baseline == "previous":
        previous = subset.iloc[1]
    else:
        if stage_tag_col not in subset.columns:
            raise ValueError(
                f"detect_regression: baseline='production' requested but "
                f"'{stage_tag_col}' column doesn't exist -- no runs are tagged."
            )
        prod_runs = subset[subset[stage_tag_col] == "production"]
        if len(prod_runs) == 0:
            raise ValueError(
                f"detect_regression: baseline='production' requested but no "
                f"run tagged {stage_tag_col}='production' found for "
                f"owner='{owner}', model='{model_name}'."
            )
        # If the latest run itself is the only production-tagged run (e.g.
        # right after a promotion), comparing it to itself would trivially
        # always report "no regression" without telling the caller why --
        # look for a DIFFERENT production run instead.
        prod_runs_excluding_latest = prod_runs[prod_runs["run_id"] != latest["run_id"]]
        if len(prod_runs_excluding_latest) == 0:
            raise ValueError(
                f"detect_regression: baseline='production' requested, but the "
                f"only production-tagged run is the latest run itself "
                f"(run_id={latest['run_id']}) -- there is no distinct prior "
                f"production run to compare against."
            )
        previous = prod_runs_excluding_latest.iloc[0]
    latest_score = latest[metric_col]
    previous_score = previous[metric_col]

    if pd.isna(latest_score) or pd.isna(previous_score):
        broken_run_id = latest["run_id"] if pd.isna(latest_score) else previous["run_id"]
        raise ValueError(
            f"detect_regression: cannot compare -- run '{broken_run_id}' did "
            f"not log metric '{metric}' (value is missing/NaN). Treating a "
            f"missing metric as 'no regression' would hide a broken run "
            f"instead of flagging it."
        )

    if math.isclose(latest_score, previous_score, rel_tol=1e-9, abs_tol=1e-9):
        regressed = False
    else:
        raw_diff = latest_score - previous_score
        worse_amount = raw_diff if lower_is_better else -raw_diff
        threshold_amount = abs(previous_score) * degradation_threshold
        regressed = bool(worse_amount > threshold_amount)

    message = (
        f"REGRESSION DETECTED: {model_name} ({owner})'s latest {metric} "
        f"({latest_score:.4f}) is worse than the {baseline} run "
        f"({previous_score:.4f})."
        if regressed else
        f"No regression: {model_name} ({owner})'s latest {metric} "
        f"({latest_score:.4f}) is not worse than the {baseline} run "
        f"({previous_score:.4f})."
    )

    return {
        "regressed": regressed,
        "previous_score": previous_score,
        "latest_score": latest_score,
        "previous_run_id": previous["run_id"],
        "latest_run_id": latest["run_id"],
        "baseline": baseline,
        "message": message,
    }