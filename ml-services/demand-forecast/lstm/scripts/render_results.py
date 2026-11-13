"""Print README result tables from output/*.json.

Run from the lstm folder:
python scripts/render_results.py
"""

import json
from pathlib import Path

OUT = Path("output")


def load(name):
    path = OUT / name
    if not path.exists():
        raise FileNotFoundError(f"Required results file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(value):
    return "n/a" if value is None else f"{value:.4f}"


def table(headers, rows):
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "---|" * len(headers),
    ]
    lines += [
        "| " + " | ".join(str(cell) for cell in row) + " |"
        for row in rows
    ]
    return "\n".join(lines)


wf = load("walk_forward_summary.json")
print("### Walk-forward folds\n")
print(table(
    ["Fold", "Train end", "Train windows", "Global MAE",
     "Per-SKU MAE", "Eligible SKUs"],
    [
        [
            fold["fold"],
            fold["train_end"],
            fold["train_windows"],
            fmt(fold["global_common_sku_metrics"]["MAE"]),
            fmt(fold["per_sku_common_metrics"]["MAE"]),
            fold["eligible_skus"],
        ]
        for fold in wf["folds"]
    ],
))
print("\nMean common-SKU MAE:")
print(
    "Global:",
    fmt(wf["mean_fold_metrics"]["global_common_eligible_skus"]["MAE"]),
)
print(
    "Per-SKU:",
    fmt(wf["mean_fold_metrics"]["per_sku_common_eligible_skus"]["MAE"]),
)

st = load("stacked_ensemble_metrics.json")
print(f"\n### Stacked ensemble (data_seed={st['data_seed']})\n")
print(table(
    ["Model", "MAE", "RMSE", "MAPE"],
    [
        [
            name,
            fmt(metrics["MAE"]),
            fmt(metrics["RMSE"]),
            fmt(metrics["MAPE"]),
        ]
        for name, metrics in st["metrics"].items()
    ],
))

robust = load("stacking_robustness_summary.json")
print(f"\n### Stacking robustness ({robust['runs']} seeds)\n")
print(table(
    ["Model", "MAE mean ± std", "RMSE mean ± std", "MAPE mean ± std"],
    [
        [
            name,
            f"{values['MAE']['mean']:.4f} ± {values['MAE']['std']:.4f}",
            f"{values['RMSE']['mean']:.4f} ± {values['RMSE']['std']:.4f}",
            f"{values['MAPE']['mean']:.4f} ± {values['MAPE']['std']:.4f}",
        ]
        for name, values in robust["results"].items()
    ],
))

cs = load("short_history_cold_start_summary.json")
print("\n### Cold-start (held-out SKUs)\n")
print(table(
    ["Model", "MAE", "RMSE", "MAPE"],
    [
        [
            name,
            fmt(metrics["mae"]),
            fmt(metrics["rmse"]),
            fmt(metrics["mape"]),
        ]
        for name, metrics in cs["metrics"].items()
    ],
))
