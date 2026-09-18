import math

from .metrics import HIGHER_IS_BETTER_METRICS, KNOWN_METRICS


def generate_leaderboard(results: dict, metric: str, lower_is_better: bool = None,
                            metadata: dict = None) -> list:
    """
    results = {"prophet": {...metrics}, "xgboost": {...metrics}, ...}
    Ranks all models by the given metric, best first.

    Refuses to rank if:
    - the metric is unrecognized (not in KNOWN_METRICS) AND lower_is_better
      wasn't explicitly given -- previously, an unknown metric like "r2"
      silently defaulted to lower-is-better, ranking it backwards. Now the
      caller must either use a known metric name or say explicitly which
      direction is better.
    - the requested metric is missing from any model's results
    - any model's value for that metric isn't numeric, is a bool, is NaN,
      or is infinite
    - fewer than 2 models have that metric
    - metadata is provided and models disagree on dataset_id, test window/
      horizon, or metric units

    IMPORTANT: metadata is optional. Without it, this function cannot
    detect scale mismatches (e.g. one model reporting MAPE as a fraction
    like 0.0264, another as a percentage like 3.64) -- both are valid
    finite numbers for the same metric NAME, so numeric validation alone
    can't catch this. Pass metadata with a "units" key whenever there's
    any chance models used different scales or conventions.

    metadata: optional {model_name: {"dataset_id": ..., "horizon": ...,
        "units": ...}}. If provided, all models must agree on every key
        present, or the ranking is refused with a clear message naming the
        mismatch.

    lower_is_better: required if `metric` is not in KNOWN_METRICS (see
        metrics.py). If given for a KNOWN metric, an explicit value that
        CONTRADICTS the known direction is rejected -- silently letting a
        caller force MAPE to rank higher-is-better would defeat this guard.

    Returns a list of (model_name, score) tuples, sorted best-first.
    Raises ValueError with a clear message if ranking isn't possible.
    """
    if not results:
        raise ValueError("No results provided to rank.")

    metric_key = metric.lower()
    is_known = metric_key in KNOWN_METRICS

    if not is_known and lower_is_better is None:
        raise ValueError(
            f"Cannot rank: '{metric}' is not a recognized metric, and no "
            f"lower_is_better direction was given. Pass lower_is_better=True "
            f"or lower_is_better=False explicitly for unrecognized metrics -- "
            f"the framework will not guess, since guessing wrong silently "
            f"ranks results backwards. Known metrics: {sorted(KNOWN_METRICS)}."
        )

    known_direction_higher = metric_key in HIGHER_IS_BETTER_METRICS
    if lower_is_better is not None and is_known:
        requested_higher_is_better = not lower_is_better
        if known_direction_higher and requested_higher_is_better is False:
            raise ValueError(
                f"Cannot rank: '{metric}' is a known higher-is-better metric, but "
                f"lower_is_better=True was explicitly requested, which contradicts it."
            )
        if not known_direction_higher and requested_higher_is_better is True:
            raise ValueError(
                f"Cannot rank: '{metric}' is a known lower-is-better metric, but "
                f"lower_is_better=False was explicitly requested, which contradicts it."
            )

    if lower_is_better is None:
        lower_is_better = not known_direction_higher

    missing = [m for m in results if metric not in results[m]]
    if missing:
        raise ValueError(
            f"Cannot rank: metric '{metric}' is missing for model(s) {missing}. "
            f"All models must report the same metric to be ranked together."
        )

    scored = [(model, results[model][metric]) for model in results]

    invalid = [
        m for m, v in scored
        if not isinstance(v, (int, float))
        or isinstance(v, bool)
        or not math.isfinite(v)
    ]
    if invalid:
        raise ValueError(
            f"Cannot rank: metric '{metric}' has non-numeric, NaN, or infinite "
            f"value(s) for model(s) {invalid}."
        )

    if len(scored) < 2:
        raise ValueError("Need at least 2 models with this metric to build a leaderboard.")

    if metadata:
        _check_metadata_compatible(metadata, list(results.keys()))
    else:
        import warnings as _warnings
        _warnings.warn(
            f"generate_leaderboard: ranking '{metric}' without metadata. "
            f"Models could be on different scales or units (e.g. a fractional "
            f"vs. percentage MAPE) and this cannot be detected without "
            f"metadata. Pass metadata with a 'units' key when there's any "
            f"chance of a scale mismatch.",
            stacklevel=2,
        )
    scored.sort(key=lambda pair: pair[1], reverse=not lower_is_better)
    return scored


def _check_metadata_compatible(metadata: dict, model_names: list) -> None:
    """Checks all models share metadata in metadata dict, refusing the
    ranking with a clear message if any key differs (e.g. one model was
    evaluated on a different dataset, test horizon, or reports its metric
    in different units than the others).
    """
    missing_metadata = [m for m in model_names if m not in metadata]
    if missing_metadata:
        raise ValueError(
            f"Cannot rank: metadata not provided for model(s) {missing_metadata}."
        )

    reference_model = model_names[0]
    reference_meta = metadata[reference_model]

    for key in reference_meta:
        values = {m: metadata[m].get(key) for m in model_names}
        distinct = set(values.values())
        if len(distinct) > 1:
            raise ValueError(
                f"Cannot rank: models disagree on '{key}' ({values}). "
                f"Models must share the same dataset, test window/horizon, "
                f"and metric units to be meaningfully compared."
            )


def print_leaderboard(results: dict, metric: str, lower_is_better: bool = None,
                         metadata: dict = None) -> None:
    """Prints a ranked leaderboard for the given metric, or a clear error if
    the models' results aren't comparable on that metric.
    """
    try:
        ranked = generate_leaderboard(results, metric, lower_is_better, metadata)
    except ValueError as e:
        print(f"Cannot generate leaderboard: {e}")
        return

    if lower_is_better is None:
        lower_is_better = metric.lower() not in HIGHER_IS_BETTER_METRICS

    print(f"Leaderboard ({metric}, {'lower' if lower_is_better else 'higher'} is better):")
    print("-" * 40)
    for rank, (model, score) in enumerate(ranked, start=1):
        print(f"{rank}. {model:<20} {score:.4f}")