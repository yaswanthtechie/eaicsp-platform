# regressor_ablation.py
"""
Prophet regressor ablation study (Round 9-11, Milestone 2).

Question: which external regressors actually help?

Method
------
1. Rolling-origin backtest: every experiment is scored on the SAME
   BACKTEST_CUTOFFS, each forecasting HORIZON_MONTHS ahead with a model
   trained only on data before the cutoff. One short holdout is too
   noisy to separate small effects.
2. Experiments: all regressors (baseline), each regressor removed on its
   own, and no regressors at all (plain Prophet).
3. Noise band: the baseline is re-run with NOISE_SEEDS different random
   draws of weather_index (itself a random mock feature). The spread of
   those MAPEs is how much the result moves from randomness alone.
   A regressor only counts as helping or hurting if removing it moves
   MAPE by MORE than that whole spread.
4. Every experiment is logged to MLflow.

Metrics are kept unrounded until they are written out, so small
differences are not lost or flipped by rounding.
"""

from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error

from src.data import load_sales_data
from src.external_regressors import (
    add_external_regressors,
    validate_external_regressors,
)
from src.train_prophet import (
    EXTERNAL_REGRESSORS,
    predict_prophet,
    train_prophet,
)


# ============================================================
# Configuration (no magic numbers elsewhere)
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RESULTS_DIR = PROJECT_ROOT / "models" / "regressor_ablation"
RESULTS_PATH = RESULTS_DIR / "ablation_results.csv"
NOISE_PATH = RESULTS_DIR / "noise_band.csv"

MLFLOW_EXPERIMENT = "demand_forecast_regressor_ablation"

# Rolling-origin backtest on monthly data: 5 cutoffs, one per year,
# each forecasting the following 12 months (60 scored months in total).
BACKTEST_CUTOFFS = [
    "2011-06-01",
    "2012-06-01",
    "2013-06-01",
    "2014-06-01",
    "2015-06-01",
]
HORIZON_MONTHS = 12

# Seeds for re-drawing the random weather_index to measure noise.
NOISE_SEEDS = [0, 1, 2, 3, 4]


# ============================================================
# Experiments
# ============================================================

def build_ablation_experiments():
    """
    Baseline (all regressors), leave-one-out for each regressor,
    and no regressors at all.
    """

    experiments = [
        {
            "experiment": "baseline",
            "removed_regressor": None,
            "regressors": EXTERNAL_REGRESSORS.copy(),
        }
    ]

    for removed_regressor in EXTERNAL_REGRESSORS:
        experiments.append(
            {
                "experiment": f"remove_{removed_regressor}",
                "removed_regressor": removed_regressor,
                "regressors": [
                    r for r in EXTERNAL_REGRESSORS
                    if r != removed_regressor
                ],
            }
        )

    experiments.append(
        {
            "experiment": "no_regressors",
            "removed_regressor": "all",
            "regressors": [],
        }
    )

    return experiments


# ============================================================
# Data
# ============================================================

def prepare_dataset():
    """Load sales data, add the external regressors, rename for Prophet."""

    df = add_external_regressors(load_sales_data())
    validate_external_regressors(df)

    prophet_df = df.rename(
        columns={"date": "ds", "quantity_sold": "y"}
    ).copy()
    prophet_df["ds"] = pd.to_datetime(prophet_df["ds"])

    return prophet_df.sort_values("ds").reset_index(drop=True)


def with_weather_seed(df, seed):
    """Return a copy whose weather_index is a fresh random draw."""

    data = df.copy()
    data["weather_index"] = np.random.default_rng(seed).uniform(
        0.0, 1.0, len(data)
    )
    return data


def split_at_cutoff(df, cutoff, horizon_months=HORIZON_MONTHS):
    """Train on everything before cutoff; test on the next horizon_months."""

    cutoff = pd.Timestamp(cutoff)
    end = cutoff + pd.DateOffset(months=horizon_months)

    train_df = df[df["ds"] < cutoff].copy()
    test_df = df[(df["ds"] >= cutoff) & (df["ds"] < end)].copy()

    if train_df.empty or test_df.empty:
        raise ValueError(f"Cutoff {cutoff.date()} leaves an empty train or test set.")

    return train_df, test_df


# ============================================================
# Metrics (unrounded)
# ============================================================

def score(actual, predicted):
    """Unrounded MAPE (%) and RMSE."""

    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)

    return {
        "MAPE": float(np.mean(np.abs((actual - predicted) / actual)) * 100),
        "RMSE": float(np.sqrt(mean_squared_error(actual, predicted))),
    }


def calculate_delta(baseline_value, experiment_value):
    """Positive delta = the metric got worse (increased) vs baseline."""

    return float(experiment_value - baseline_value)


def backtest(df, regressors):
    """
    Score one regressor set on every cutoff.

    Returns the mean MAPE and RMSE across cutoffs.
    """

    mapes, rmses = [], []

    for cutoff in BACKTEST_CUTOFFS:
        train_df, test_df = split_at_cutoff(df, cutoff)

        model = train_prophet(train_df, regressors=regressors, save_model=False)
        forecast = predict_prophet(model, test_df, regressors=regressors)

        merged = test_df[["ds", "y"]].merge(forecast, on="ds", how="inner")
        if merged.empty:
            raise ValueError(f"No forecast rows matched at cutoff {cutoff}.")

        metrics = score(merged["y"], merged["yhat"])
        mapes.append(metrics["MAPE"])
        rmses.append(metrics["RMSE"])

    return {
        "MAPE": float(np.mean(mapes)),
        "RMSE": float(np.mean(rmses)),
    }


# ============================================================
# Interpretation
# ============================================================

def noise_band(noise_mapes):
    """
    Full max-min spread of the baseline MAPE across random seeds.

    Two runs that differ ONLY by random noise can land this far apart,
    so an ablation delta must exceed the whole spread to count as real.
    """

    values = np.asarray(noise_mapes, dtype=float)
    return float(values.max() - values.min())


def interpret_result(row, band):
    """
    Describe an experiment relative to baseline, honestly.

    A change smaller than the noise band is reported as no measurable
    effect. This does NOT claim causality.
    """

    if row["experiment"] == "baseline":
        return "Baseline with all regressors."

    delta = row["delta_MAPE"]
    what = (
        "Removing all regressors"
        if row["experiment"] == "no_regressors"
        else f"Removing {row['removed_regressor']}"
    )

    if abs(delta) <= band:
        return (
            f"{what} changed MAPE by {delta:+.2f}pp, within the "
            f"+/-{band:.2f}pp noise band: no measurable effect."
        )

    if delta > 0:
        return f"{what} worsened MAPE by {delta:+.2f}pp (beyond noise): it helps."

    return f"{what} improved MAPE by {delta:+.2f}pp (beyond noise): it hurts."


# ============================================================
# Study
# ============================================================

def run_ablation_study():
    """Run the ablation, measure the noise band, log to MLflow, save CSVs."""

    df = prepare_dataset()
    experiments = build_ablation_experiments()

    mlflow.set_experiment(MLFLOW_EXPERIMENT)

    with mlflow.start_run(run_name="regressor_ablation_study"):
        mlflow.log_params(
            {
                "backtest_cutoffs": ",".join(BACKTEST_CUTOFFS),
                "horizon_months": HORIZON_MONTHS,
                "noise_seeds": ",".join(map(str, NOISE_SEEDS)),
                "all_regressors": ",".join(EXTERNAL_REGRESSORS),
            }
        )

        # 1. Noise band: baseline with different random weather draws
        noise_rows = []
        for seed in NOISE_SEEDS:
            metrics = backtest(with_weather_seed(df, seed), EXTERNAL_REGRESSORS)
            noise_rows.append({"weather_seed": seed, **metrics})

        noise = pd.DataFrame(noise_rows)
        band = noise_band(noise["MAPE"])
        mlflow.log_metric("noise_band_mape_pp", band)

        # 2. Ablation experiments (same data and cutoffs for every one)
        rows = []
        for experiment in experiments:
            with mlflow.start_run(run_name=experiment["experiment"], nested=True):
                metrics = backtest(df, experiment["regressors"])

                mlflow.log_params(
                    {
                        "removed_regressor": experiment["removed_regressor"] or "none",
                        "regressors_used": ",".join(experiment["regressors"]) or "none",
                    }
                )
                mlflow.log_metrics({"mape": metrics["MAPE"], "rmse": metrics["RMSE"]})

            rows.append(
                {
                    "experiment": experiment["experiment"],
                    "removed_regressor": experiment["removed_regressor"],
                    "regressors_used": ", ".join(experiment["regressors"]) or "none",
                    **metrics,
                }
            )

        results = pd.DataFrame(rows)
        baseline = results.loc[results["experiment"] == "baseline"].iloc[0]

        results["delta_MAPE"] = results["MAPE"].apply(
            lambda v: calculate_delta(baseline["MAPE"], v)
        )
        results["delta_RMSE"] = results["RMSE"].apply(
            lambda v: calculate_delta(baseline["RMSE"], v)
        )
        results["noise_band_pp"] = band
        results["interpretation"] = results.apply(
            lambda row: interpret_result(row, band), axis=1
        )

        # 3. Save (round only for the written files)
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        results.round(4).to_csv(RESULTS_PATH, index=False)
        noise.round(4).to_csv(NOISE_PATH, index=False)

        mlflow.log_artifact(str(RESULTS_PATH))
        mlflow.log_artifact(str(NOISE_PATH))

    print(results.round(3).to_string(index=False))
    print(f"\nNoise band: +/-{band:.3f}pp MAPE (from {len(NOISE_SEEDS)} random weather draws)")
    print(f"Results saved to: {RESULTS_PATH}")

    return results, noise


if __name__ == "__main__":
    run_ablation_study()