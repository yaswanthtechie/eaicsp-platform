import math

from .metrics import HIGHER_IS_BETTER_METRICS


def generate_leaderboard(results: dict, metric: str, lower_is_better: bool = None,
                            metadata: dict = None) -> list:
    """
    results = {"prophet": {...metrics}, "xgboost": {...metrics}, ...}
    Ranks all models by the given metric, best first.

    Refuses to rank if:
    - the requested metric is missing from any model's results
    - any model's value for that metric isn't numeric, is a bool, is NaN,
      or is infinite (math.isfinite catches NaN AND +/-Infinity in one check)
    - fewer than 2 models have that metric
    - metadata is provided and models disagree on dataset_id, test window/
      horizon, or metric units -- ranking models evaluated on different
      data, windows, or scales is not a meaningful comparison even if the
      raw numbers both happen to be valid floats

    metadata: optional {model_name: {"dataset_id": ..., "horizon": ...,
        "units": ...}}. If provided, all models must agree on every key
        present, or the ranking is refused with a clear message naming the
        mismatch.

    lower_is_better: optional override. If not given, inferred automatically
        from the shared HIGHER_IS_BETTER_METRICS set in metrics.py. An
        explicit override that CONTRADICTS the known direction for a metric
        already in HIGHER_IS_BETTER_METRICS is rejected -- silently letting
        a caller force MAPE to rank higher-is-better would defeat the whole
        point of this guard.

    Returns a list of (model_name, score) tuples, sorted best-first.
    Raises ValueError with a clear message if ranking isn't possible.
    """
    if not results:
        raise ValueError("No results provided to rank.")

    known_direction_higher = metric in HIGHER_IS_BETTER_METRICS
    if lower_is_better is not None:
        requested_higher_is_better = not lower_is_better
        if metric in HIGHER_IS_BETTER_METRICS and requested_higher_is_better is False:
            raise ValueError(
                f"Cannot rank: '{metric}' is a known higher-is-better metric, but "
                f"lower_is_better=True was explicitly requested, which contradicts it."
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
        lower_is_better = metric not in HIGHER_IS_BETTER_METRICS

    print(f"Leaderboard ({metric}, {'lower' if lower_is_better else 'higher'} is better):")
    print("-" * 40)
    for rank, (model, score) in enumerate(ranked, start=1):
        print(f"{rank}. {model:<20} {score:.4f}")