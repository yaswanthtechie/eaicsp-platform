import json
import os

import pandas as pd

from src.config import OUTPUT_DIR
from src.stacked_ensemble import run_stacked_ensemble

SEEDS = [11, 21, 42, 77, 123]
rows = []

for seed in SEEDS:
    print(f"\n{'=' * 60}")
    print(f"ROBUSTNESS RUN: seed={seed}")
    print(f"{'=' * 60}")

    report = run_stacked_ensemble(
        data_seed=seed,
        model_seed=seed,
    )

    for model_name, values in report["metrics"].items():
        row = {
            "seed": seed,
            "model": model_name,
        }
        row.update(values)
        rows.append(row)

os.makedirs(OUTPUT_DIR, exist_ok=True)

raw_path = os.path.join(OUTPUT_DIR, "stacking_robustness_runs.csv")
summary_path = os.path.join(OUTPUT_DIR, "stacking_robustness_summary.csv")
report_path = os.path.join(OUTPUT_DIR, "stacking_robustness_summary.json")

raw = pd.DataFrame(rows)
raw.to_csv(raw_path, index=False)

metric_columns = [
    c for c in raw.columns
    if c not in ("seed", "model")
]

summary = raw.groupby("model")[metric_columns].agg(
    ["mean", "std", "min", "max"]
)
summary.to_csv(summary_path)

json_summary = {}
for model_name, group in raw.groupby("model"):
    json_summary[model_name] = {}
    for metric in metric_columns:
        values = group[metric].astype(float)
        json_summary[model_name][metric] = {
            "mean": float(values.mean()),
            "std": float(values.std(ddof=1)),
            "min": float(values.min()),
            "max": float(values.max()),
        }

with open(report_path, "w", encoding="utf-8") as f:
    json.dump(
        {
            "seeds": SEEDS,
            "runs": len(SEEDS),
            "results": json_summary,
        },
        f,
        indent=2,
    )

print("\n=== ROBUSTNESS SUMMARY: mean and standard deviation ===")
print(summary.round(4).to_string())
print(f"\nSaved raw runs: {raw_path}")
print(f"Saved summary CSV: {summary_path}")
print(f"Saved summary JSON: {report_path}")
