def compare_models(results: dict) -> None:
    """
    results = {"prophet": {...metrics}, "xgboost": {...metrics}, "naive": {...metrics}}
    Prints a clean side-by-side table. Highlights the winner per metric.
    """
    metrics_names = list(next(iter(results.values())).keys())
    model_names = list(results.keys())

    header = f"{'Metric':<15}" + "".join(f"{m:<15}" for m in model_names)
    print(header)
    print("-" * len(header))

    for metric in metrics_names:
        values = {m: results[m][metric] for m in model_names}
        winner = min(values, key=values.get)
        row = f"{metric:<15}"
        for m in model_names:
            mark = " *" if m == winner else ""
            row += f"{values[m]:<13.2f}{mark}"
        print(row)