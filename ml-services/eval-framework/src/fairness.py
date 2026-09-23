import pandas as pd

from .metrics import HIGHER_IS_BETTER_METRICS, mape, rmse, accuracy


# Single source of truth for what evaluate_by_slice can compute. A metric
# name not in this dict is refused with one clear error -- no separate
# "known but unsupported" vs "unknown" distinction to confuse callers.
_METRIC_FUNCTIONS = {
    "mape": mape,
    "rmse": rmse,
    "accuracy": accuracy,
}


def evaluate_by_slice(df: pd.DataFrame, slice_col: str, actual_col: str, predicted_col: str,
                        metric: str, lower_is_better: bool = None,
                        degradation_threshold: float = 0.20, min_slice_size: int = 5) -> dict:
    """
    Computes a metric separately for each slice of data (e.g. per warehouse,
    per category) and for the dataset overall, then flags any slice that
    performs meaningfully worse than the overall result. This is the honest
    counterpart to aggregate metrics: a model can look fine on average while
    quietly failing on one subgroup, invisible unless someone deliberately
    checks per-slice.

    df: the full dataset, one row per prediction
    slice_col: column identifying which slice each row belongs to
    actual_col, predicted_col: columns holding true and predicted values
    metric: one of _METRIC_FUNCTIONS ("mape", "rmse", "accuracy"). An
        unsupported metric is refused with a clear message listing what IS
        supported -- never silently assumed, since a wrong assumption here
        would hide a real disparity instead of surfacing it.
    lower_is_better: optional explicit override. If not given, inferred from
        HIGHER_IS_BETTER_METRICS.
    degradation_threshold: fraction worse than overall a slice's score must
        be before it's flagged. Default 0.20 = "20% worse than overall".
    min_slice_size: slices with fewer rows than this are reported but never
        flagged -- too few rows to draw a reliable conclusion.

    Rows with a NaN slice_col value are excluded from slicing (reported
    separately as "unassigned") rather than silently dropped, since a
    silently-dropped NaN slice could hide exactly the kind of gap this
    function exists to catch.

    Returns:
    {
        "overall_score": float,
        "slices": {slice_value: {"score": float, "n": int, "flagged": bool}},
        "flagged_slices": [slice_value, ...],
        "unassigned_rows": int,
        "summary": str,
    }

    Raises ValueError if the dataframe or any required column is missing,
    or if the metric isn't supported.
    """
    if len(df) == 0:
        raise ValueError("evaluate_by_slice: dataframe is empty.")

    for col in (slice_col, actual_col, predicted_col):
        if col not in df.columns:
            raise ValueError(f"evaluate_by_slice: column '{col}' not found in dataframe.")

    metric_key = metric.lower()
    if metric_key not in _METRIC_FUNCTIONS:
        raise ValueError(
            f"evaluate_by_slice: '{metric}' is not supported. Supported "
            f"metrics: {sorted(_METRIC_FUNCTIONS.keys())}."
        )
    metric_fn = _METRIC_FUNCTIONS[metric_key]

    if lower_is_better is None:
        lower_is_better = metric_key not in HIGHER_IS_BETTER_METRICS

    unassigned_rows = int(df[slice_col].isna().sum())
    df_assigned = df[df[slice_col].notna()]
    if len(df_assigned) == 0:
        raise ValueError("evaluate_by_slice: every row has a missing slice_col value.")

    overall_score = metric_fn(df_assigned[actual_col].tolist(), df_assigned[predicted_col].tolist())

    slices = {}
    flagged_slices = []

    for slice_value, slice_df in df_assigned.groupby(slice_col):
        n = len(slice_df)
        try:
            slice_score = metric_fn(slice_df[actual_col].tolist(), slice_df[predicted_col].tolist())
        except ValueError as e:
            slices[slice_value] = {"score": None, "n": n, "flagged": False, "error": str(e)}
            continue

        is_flagged = False
        if n >= min_slice_size:
            if lower_is_better:
                is_flagged = slice_score > overall_score * (1 + degradation_threshold)
            else:
                is_flagged = slice_score < overall_score * (1 - degradation_threshold)

        slices[slice_value] = {"score": slice_score, "n": n, "flagged": is_flagged}
        if is_flagged:
            flagged_slices.append(slice_value)

    if flagged_slices:
        summary = (
            f"{len(flagged_slices)} of {len(slices)} slice(s) flagged as "
            f"performing meaningfully worse than the overall {metric} "
            f"({overall_score:.4f}): {flagged_slices}."
        )
    else:
        summary = (
            f"No slices flagged -- all {len(slices)} slice(s) are within "
            f"{degradation_threshold:.0%} of the overall {metric} ({overall_score:.4f})."
        )
    if unassigned_rows:
        summary += f" ({unassigned_rows} row(s) had a missing {slice_col} value and were excluded.)"

    return {
        "overall_score": overall_score,
        "slices": slices,
        "flagged_slices": flagged_slices,
        "unassigned_rows": unassigned_rows,
        "summary": summary,
    }