"""Leakage-free, time-ordered stacking for Prophet, XGBoost and LSTM."""

import json
import os
from pathlib import Path


import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
ROOT = Path(__file__).resolve().parent.parent
from src.config import DATASET_DAYS, OUTPUT_DIR, RANDOM_SEED
from src.data import generate_data
from src.ensemble import (
    MODEL_NAMES,
    check_contiguous,
    fit_lstm_and_predict,
    fit_prophet_and_predict,
    fit_xgboost_and_predict,
    set_seeds,
)
from src.evaluate import calculate_metrics


BASE_COLUMNS = list(MODEL_NAMES)
DEFAULT_BLOCK_SIZE = 28
META_ALPHA = 1.0


def _predict_base_models(history_df, forecast_df):
    """Predict a future block using history strictly before that block."""
    check_contiguous(history_df, forecast_df)

    predictions = {
        "Prophet": np.asarray(
            fit_prophet_and_predict(history_df, forecast_df)
        ).reshape(-1),
        "XGBoost": np.asarray(
            fit_xgboost_and_predict(history_df, forecast_df)
        ).reshape(-1),
        "LSTM": np.asarray(
            fit_lstm_and_predict(history_df, forecast_df)
        ).reshape(-1),
    }

    expected = len(forecast_df)
    for name, values in predictions.items():
        if len(values) != expected:
            raise ValueError(
                f"{name} returned {len(values)} predictions; "
                f"expected {expected}."
            )
        if not np.isfinite(values).all():
            raise ValueError(f"{name} returned non-finite predictions.")

    return predictions


def generate_oof_predictions(
    df,
    start_idx,
    end_idx,
    block_size=DEFAULT_BLOCK_SIZE,
):
    """
    Generate time-ordered out-of-fold predictions.

    Each forecast block is predicted by models trained only on rows
    strictly earlier than the block. Blocks do not overlap.
    """
    if not 0 < start_idx < end_idx <= len(df):
        raise ValueError("Require 0 < start_idx < end_idx <= len(df).")
    if block_size < 1:
        raise ValueError("block_size must be positive.")

    records = []

    for block_start in range(start_idx, end_idx, block_size):
        block_end = min(block_start + block_size, end_idx)

        history_df = df.iloc[:block_start].copy()
        forecast_df = df.iloc[block_start:block_end].copy()

        if history_df.empty or forecast_df.empty:
            raise ValueError("History and forecast blocks must be non-empty.")

        predictions = _predict_base_models(history_df, forecast_df)

        block = pd.DataFrame({
            "Date": forecast_df["Date"].to_numpy(),
            "Actual": forecast_df["Demand"].to_numpy(),
            **predictions,
        })
        records.append(block)

    result = pd.concat(records, ignore_index=True)

    if result["Date"].duplicated().any():
        raise AssertionError("OOF forecast dates must not overlap.")

    return result


def fit_meta_learner(oof_predictions, alpha=META_ALPHA):
    """Fit Ridge using OOF predictions only, never final-test predictions."""
    required = {"Actual", *BASE_COLUMNS}
    missing = required.difference(oof_predictions.columns)
    if missing:
        raise ValueError(f"Missing OOF columns: {sorted(missing)}")
    if len(oof_predictions) < 2:
        raise ValueError("At least two OOF rows are required.")

    X_oof = oof_predictions[BASE_COLUMNS].to_numpy(dtype=float)
    y_oof = oof_predictions["Actual"].to_numpy(dtype=float)

    if not np.isfinite(X_oof).all() or not np.isfinite(y_oof).all():
        raise ValueError("OOF data contains non-finite values.")

    model = Ridge(alpha=alpha)
    model.fit(X_oof, y_oof)
    return model


def evaluate_test_predictions(test_predictions, meta_model):
    """Compare every method on exactly the same held-out test dates."""
    result = test_predictions.copy()

    result["EqualWeightAverage"] = result[BASE_COLUMNS].mean(axis=1)
    result["StackedRidge"] = meta_model.predict(
        result[BASE_COLUMNS].to_numpy(dtype=float)
    )

    actual = result["Actual"].to_numpy(dtype=float)
    methods = BASE_COLUMNS + ["EqualWeightAverage", "StackedRidge"]

    metrics = {
        name: calculate_metrics(actual, result[name].to_numpy(dtype=float))
        for name in methods
    }

    return result, metrics


def run_stacked_ensemble(block_size=DEFAULT_BLOCK_SIZE, data_seed=42, model_seed=RANDOM_SEED):
    """
    Use the existing single-series synthetic dataset.

    First 60%: initial history / warm-up.
    Next 25%: OOF data for fitting the meta-learner.
    Final 15%: held-out rolling-origin test.
    """
    set_seeds(model_seed)
    df = generate_data(days=DATASET_DAYS, seed=data_seed).reset_index(drop=True)

    if not {"Date", "Demand"}.issubset(df.columns):
        raise ValueError("Expected the dataset columns Date and Demand.")

    df["Date"] = pd.to_datetime(df["Date"])
    if not df["Date"].is_monotonic_increasing:
        raise ValueError("Dataset dates must be in chronological order.")
    if df["Date"].duplicated().any():
        raise ValueError("Dataset dates must be unique.")

    n_rows = len(df)
    oof_start = int(n_rows * 0.60)
    test_start = int(n_rows * 0.85)

    if oof_start < 2 or test_start <= oof_start or test_start >= n_rows:
        raise ValueError("Dataset is too small for the configured split.")

    # Every OOF block is predicted using only the history before that block.
    oof_predictions = generate_oof_predictions(
        df, oof_start, test_start, block_size
    )

    # Final test rows are not used to fit or tune the meta-learner.
    meta_model = fit_meta_learner(oof_predictions)

    # Rolling-origin test: later blocks may use actual observations from
    # earlier test blocks as history, but never actuals inside their own block.
    test_predictions = generate_oof_predictions(
        df, test_start, n_rows, block_size
    )

    test_results, metrics = evaluate_test_predictions(
        test_predictions, meta_model
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    oof_path = os.path.join(OUTPUT_DIR, "stacked_oof_predictions.csv")
    test_path = os.path.join(OUTPUT_DIR, "stacked_test_predictions.csv")
    metrics_path = os.path.join(OUTPUT_DIR, "stacked_ensemble_metrics.json")

    oof_predictions.to_csv(oof_path, index=False)
    test_results.to_csv(test_path, index=False)

    report = {
        "dataset": "generate_data(days=DATASET_DAYS)",
        "dataset_rows": n_rows,
        "data_seed": data_seed,
        "model_seed": model_seed,
        "initial_history_rows": oof_start,
        "oof_rows": len(oof_predictions),
        "test_rows": len(test_results),
        "block_size_days": block_size,
        "meta_learner": "Ridge",
        "meta_alpha": META_ALPHA,
        "oof_start_date": str(oof_predictions["Date"].min().date()),
        "oof_end_date": str(oof_predictions["Date"].max().date()),
        "test_start_date": str(test_results["Date"].min().date()),
        "test_end_date": str(test_results["Date"].max().date()),
        "metrics": metrics,
        "ridge_coefficients": {
            name: float(value)
            for name, value in zip(BASE_COLUMNS, meta_model.coef_)
        },
        "ridge_intercept": float(meta_model.intercept_),
        "artifacts": {
            "oof_predictions": os.path.relpath(oof_path, ROOT),
            "test_predictions": os.path.relpath(test_path, ROOT),
        },
    }

    with open(metrics_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print("\n=== Leakage-Free Stacked Ensemble ===")
    print(f"Dataset rows: {n_rows}")
    print(f"OOF rows: {len(oof_predictions)}")
    print(f"Final test rows: {len(test_results)}")
    print(f"OOF date range: {report['oof_start_date']} to "
          f"{report['oof_end_date']}")
    print(f"Test date range: {report['test_start_date']} to "
          f"{report['test_end_date']}")
    print("\nFinal test metrics:")
    print(pd.DataFrame(metrics).T.round(4).to_string())
    print("\nRidge coefficients:")
    print(report["ridge_coefficients"])
    print(f"\nSaved report: {metrics_path}")

    return report


if __name__ == "__main__":
    run_stacked_ensemble()
