def compare_models(results: dict) -> None:
    """
    results = {"prophet": {...metrics}, "xgboost": {...metrics}, "naive":
    {...metrics}}
    Prints a clean side by side table. Highlights the winner per metric.
    Models missing a given metric show as "N/A" in that row instead of crashing,
    and are excluded from winner selection for that metric.
    """
    HIGHER_IS_BETTER = {"precision", "recall", "f1"}

    if not results:
        print("No results to compare.")
        return

    all_metrics = []
    for model_metrics in results.values():
        for metric in model_metrics:
            if metric not in all_metrics:
                all_metrics.append(metric)

    model_names = list(results.keys())

    header = f"{'Metric':<15}" + "".join(f"{m:<15}" for m in model_names)
    print(header)
    print("-" * len(header))

    for metric in all_metrics:
        values = {m: results[m][metric] for m in model_names if metric in results[m]}
        winner = None
        if values:
            winner = (max if metric in HIGHER_IS_BETTER else min)(values, key=values.get)

        row = f"{metric:<15}"
        for m in model_names:
            if metric in results[m]:
                cell = f"{results[m][metric]:.2f}"
                if m == winner:
                    cell += " *"
            else:
                cell = "N/A"
            row += f"{cell:<15}"
        print(row)