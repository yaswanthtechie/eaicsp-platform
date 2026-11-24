"""
Evaluate sales anomaly detection on synthetic sales with injected events.

Synthetic only: weekday seasonality, small trend, day-level over-dispersion
(gamma noise, as in the seed) on top of Poisson noise, and a share of slow
sellers; 6 known spikes (x2.5 to x4) and drops (x0 to x0.3) per series, at
least 14 days apart. Seeds and magnitudes are fixed design values, not tuned
on results. Precision and recall come from eval_framework.precision_recall
(day level, scored days only).

Two runs are reported: the realistic run (default) and the old pure Poisson
run (dispersion=None, slow_share=0.0).

Each run is logged to MLflow (see src/sales_anomaly_tracking.py): parameters,
thresholds, data range, precision and recall, anomaly count by severity. The
tracking URI comes from MLFLOW_TRACKING_URI; without it nothing is logged.
--register also registers the thresholds in force in the MLflow model registry
(one version per configuration, from the realistic run only).

Run: python -m src.sales_anomaly_eval [--register]
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from eval_framework import precision_recall

from .sales_anomaly import detect
from .sales_anomaly_tracking import (
    date_range,
    log_run,
    safe_log_run,
    severity_counts,
)

EVAL_SEED = 5151
CLEAN_SEED = 5152
N_SERIES = 40
N_DAYS = 365
EVENTS_PER_SERIES = 6
MIN_SEPARATION = 14
FIRST_EVENT_DAY = 70

DISPERSION = 8.0
SLOW_SHARE = 0.25

WAREHOUSES = [
    "WH-BLR-01",
    "WH-BOM-01",
    "WH-CCU-01",
    "WH-DEL-01",
    "WH-HYD-01",
    "WH-MAA-01",
]
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


def make_data(seed, with_events=True, dispersion=DISPERSION, slow_share=SLOW_SHARE):
    """
    Return (sales frame, labels frame with date, product, warehouse, kind).

    dispersion: gamma shape for day-level over-dispersion, as in
    data-platform/seed/demand.py:45. None gives pure Poisson.
    slow_share: share of series that sell 0.5 to 3 units a day.
    """

    rng = np.random.default_rng(seed)
    dates = pd.date_range("2025-01-06", periods=N_DAYS, freq="D")
    rows, labels = [], []
    n_slow = int(N_SERIES * slow_share)

    for i in range(N_SERIES):
        product = f"SKU-{i + 1:06d}"
        warehouse = WAREHOUSES[i % len(WAREHOUSES)]
        slow = i < n_slow
        base = rng.uniform(0.5, 3.0) if slow else rng.uniform(20, 80)
        trend = rng.uniform(-0.2, 0.3)

        lam = (
            base
            * WEEKDAY_FACTOR[dates.day_of_week.to_numpy()]
            * (1 + trend * np.arange(N_DAYS) / N_DAYS)
        )

        if dispersion:
            lam = lam * rng.gamma(dispersion, 1 / dispersion, size=N_DAYS)

        qty = rng.poisson(lam).astype(float)

        if with_events:
            for day in _event_days(rng):
                if rng.random() < 0.5:
                    bump = 6 if slow else 0
                    qty[day] = round(max(lam[day], 1.0) * rng.uniform(2.5, 4.0)) + bump
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

    label_frame = pd.DataFrame(labels, columns=["date", "product", "warehouse", "kind"])

    return pd.concat(rows, ignore_index=True), label_frame


def evaluate(
    dispersion=DISPERSION,
    slow_share=SLOW_SHARE,
    log_mlflow=False,
    run_name="sales-anomaly-eval",
    register=False,
):

    sales, labels = make_data(EVAL_SEED, dispersion=dispersion, slow_share=slow_share)
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

    clean_sales, _ = make_data(
        CLEAN_SEED,
        with_events=False,
        dispersion=dispersion,
        slow_share=slow_share,
    )
    clean, _ = detect(clean_sales)
    clean_scored = clean[clean["score"].notna()]

    rows.append(
        {
            "part": "clean_series_false_alarms",
            "scored_days": len(clean_scored),
            "flagged_days": int(clean_scored["is_anomaly"].sum()),
            "flagged_per_1000_days": round(1000 * clean_scored["is_anomaly"].mean(), 2),
        }
    )

    registration_error = None

    if log_mlflow:
        start, end = date_range(sales["sale_date"])

        # Routine tracking only warns when MLflow fails. An explicit --register
        # must not look successful when nothing was registered.
        track = log_run if register else safe_log_run

        try:
            logged = track(
                run_name,
                params={
                    "eval_seed": EVAL_SEED,
                    "clean_seed": CLEAN_SEED,
                    "dispersion": dispersion,
                    "slow_share": slow_share,
                    "n_series": N_SERIES,
                    "n_days": N_DAYS,
                    "events_per_series": EVENTS_PER_SERIES,
                },
                data_start=start,
                data_end=end,
                severities=severity_counts(flagged),
                metrics={
                    "precision": metrics["precision"],
                    "recall": metrics["recall"],
                    "f1": metrics["f1"],
                    "recall_spike": rows[1]["recall"],
                    "recall_drop": rows[2]["recall"],
                    "clean_false_alarms_per_1000": 1000
                    * clean_scored["is_anomaly"].mean(),
                },
                tags={"run_kind": "evaluation"},
                register=register,
            )

            if register and logged is None:
                raise RuntimeError("MLFLOW_TRACKING_URI is not set.")
        except Exception as error:  # noqa: BLE001 - kept and reported by --register
            registration_error = error

    result = pd.DataFrame(rows)
    result.attrs["registration_error"] = registration_error

    return result


def main(argv=None):

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--register",
        action="store_true",
        help="Register the thresholds in force in the MLflow model registry "
        "(realistic run only; needs MLFLOW_TRACKING_URI).",
    )
    args = parser.parse_args(argv)

    results_dir.mkdir(parents=True, exist_ok=True)

    runs = [
        (
            "realistic",
            {"log_mlflow": True, "register": args.register},
            "sales_anomaly_eval.csv",
        ),
        (
            "poisson (dispersion=None, slow_share=0.0)",
            {
                "dispersion": None,
                "slow_share": 0.0,
                "log_mlflow": True,
                "run_name": "sales-anomaly-eval-poisson",
            },
            "sales_anomaly_eval_poisson.csv",
        ),
    ]

    registration_error = None

    for name, kwargs, filename in runs:
        result = evaluate(**kwargs)
        registration_error = registration_error or result.attrs.get(
            "registration_error"
        )

        print(f"== {name} ==")
        print(result.to_string(index=False))
        result.to_csv(results_dir / filename, index=False)
        print(f"written: results/{filename}\n")

    if registration_error is not None:
        print(
            f"REGISTRATION FAILED: nothing was registered in MLflow: {registration_error}",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
