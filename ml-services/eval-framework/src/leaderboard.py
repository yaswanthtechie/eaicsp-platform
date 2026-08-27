def generate_leaderboard(results: dict, metric: str, lower_is_better: bool = True) -> list:
    """
    results = {"prophet": {...metrics}, "xgboost": {...metrics}, ...}
    Ranks all models by the given metric, best first.

    Refuses to rank if:
    - the requested metric is missing from any model's results
    - any model's value for that metric isn't numeric
    - fewer than 2 models have that metric

    Returns a list of (model_name, score) tuples, sorted best-first.
    Raises ValueError with a clear message if ranking isn't possible.
    """
    if not results:
        raise ValueError("No results provided to rank.")

    missing = [m for m in results if metric not in results[m]]
    if missing:
        raise ValueError(
            f"Cannot rank: metric '{metric}' is missing for model(s) {missing}. "
            f"All models must report the same metric to be ranked together."
        )

    scored = [(model, results[model][metric]) for model in results]

    non_numeric = [m for m, v in scored if not isinstance(v, (int, float))]
    if non_numeric:
        raise ValueError(
            f"Cannot rank: metric '{metric}' has non-numeric value(s) for model(s) {non_numeric}."
        )

    if len(scored) < 2:
        raise ValueError("Need at least 2 models with this metric to build a leaderboard.")

    scored.sort(key=lambda pair: pair[1], reverse=not lower_is_better)
    return scored


def print_leaderboard(results: dict, metric: str, lower_is_better: bool = True) -> None:
    """Prints a ranked leaderboard for the given metric, or a clear error if
    the models' results aren't comparable on that metric.
    """
    try:
        ranked = generate_leaderboard(results, metric, lower_is_better)
    except ValueError as e:
        print(f"Cannot generate leaderboard: {e}")
        return

    print(f"Leaderboard ({metric}, {'lower' if lower_is_better else 'higher'} is better):")
    print("-" * 40)
    for rank, (model, score) in enumerate(ranked, start=1):
        print(f"{rank}. {model:<20} {score:.4f}")