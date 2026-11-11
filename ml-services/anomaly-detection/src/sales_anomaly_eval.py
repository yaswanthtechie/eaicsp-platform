"""
Evaluate sales anomaly detection on synthetic sales with injected events.

Synthetic only: weekday seasonality, small trend, Poisson noise; 6 known
spikes (x2.5 to x4) and drops (x0 to x0.3) per series, at least 14 days
apart. Seeds and magnitudes are fixed design values, not tuned on results.
Precision and recall come from eval_framework.precision_recall (day level,
scored days only).

Run: python -m src.sales_anomaly_eval
"""

from pathlib import Path

import numpy as np
import pandas as pd
from eval_framework import precision_recall

from .sales_anomaly import detect


EVAL_SEED = 5151
CLEAN_SEED = 5152
N_SERIES = 40
N_DAYS = 365
EVENTS_PER_SERIES = 6
MIN_SEPARATION = 14
FIRST_EVENT_DAY = 70

WAREHOUSES = ["WH-BLR-01", "WH-BOM-01", "WH-CCU-01", "WH-DEL-01", "WH-HYD-01", "WH-MAA-01"]
WEEKDAY_FACTOR = np.array([1.0, 0.95, 0.95, 1.0, 1.1, 1.3, 0.8])

project_root = Path(__file__).resolve().parent.parent
results_dir = project_root / "results"


def _event_days(rng):

    candidates = rng.permutation(np.arange(FIRST_EVENT_DAY, N_DAYS - 5))
    chosen = []

    for day in candidates:
        if all(abs(day - c) >= MIN_SEPARATION for c in chosen):
            chosen.append(int(day))

        if len(chosen) == EVENTS_PER_SERIES:
            break

    return sorted(chosen)


def make_data(seed, with_events=True):
    """Return (sales frame, labels frame with date, product, warehouse, kind)."""

    rng = np.random.default_rng(seed)
    dates = pd.date_range("2025-01-06", periods=N_DAYS, freq="D")
    rows, labels = [], []

    for i in range(N_SERIES):

        product = f"SKU-{i + 1:06d}"
        warehouse = WAREHOUSES[i % len(WAREHOUSES)]
        base = rng.uniform(20, 80)
        trend = rng.uniform(-0.2, 0.3)

        lam = (
            base
            * WEEKDAY_FACTOR[dates.dayofweek.to_numpy()]
            * (1 + trend * np.arange(N_DAYS) / N_DAYS)
        )
        qty = rng.poisson(lam).astype(float)

        if with_events:
            for day in _event_days(rng):
                if rng.random() < 0.5:
                    qty[day] = round(lam[day] * rng.uniform(2.5, 4.0))
                    kind = "spike"
                else:
                    qty[day] = round(lam[day] * rng.uniform(0.0, 0.3))
                    kind = "drop"

                labels.append((dates[day], product, warehouse, kind))

        rows.append(
            pd.DataFrame(
                {
                    "sale_date": dates,
                    "sku_id": product,
                    "warehouse": warehouse,
                    "quantity_sold": qty,
                }
            )
        )

    label_frame = pd.DataFrame(
        labels, columns=["date", "product", "warehouse", "kind"]
    )

    return pd.concat(rows, ignore_index=True), label_frame


def evaluate():

    sales, labels = make_data(EVAL_SEED)
    scores, _ = detect(sales)
    scored = scores[scores["score"].notna()].merge(
        labels, on=["date", "product", "warehouse"], how="left"
    )

    y_true = scored["kind"].notna().astype(int).to_numpy()
    y_pred = scored["is_anomaly"].astype(int).to_numpy()

    metrics = precision_recall(y_true, y_pred)

    rows = [{"part": "overall", **{k: v for k, v in metrics.items()}}]

    for kind in ("spike", "drop"):
        sub = scored[scored["kind"] == kind]
        rows.append(
            {
                "part": f"recall_{kind}",
                "events": len(sub),
                "found": int(sub["is_anomaly"].sum()),
                "recall": float(sub["is_anomaly"].mean()) if len(sub) else None,
            }
        )

    flagged = scored[scored["is_anomaly"]]
    rows.append(
        {
            "part": "flagged_by_severity",
            **flagged["severity"].value_counts().to_dict(),
        }
    )

    clean_sales, _ = make_data(CLEAN_SEED, with_events=False)
    clean, _ = detect(clean_sales)
    clean_scored = clean[clean["score"].notna()]

    rows.append(
        {
            "part": "clean_series_false_alarms",
            "scored_days": len(clean_scored),
            "flagged_days": int(clean_scored["is_anomaly"].sum()),
            "flagged_per_1000_days": round(
                1000 * clean_scored["is_anomaly"].mean(), 2
            ),
        }
    )

    return pd.DataFrame(rows)


def main():

    result = evaluate()

    print(result.to_string(index=False))

    results_dir.mkdir(parents=True, exist_ok=True)
    result.to_csv(results_dir / "sales_anomaly_eval.csv", index=False)

    print("\nwritten: results/sales_anomaly_eval.csv")


if __name__ == "__main__":
    main()