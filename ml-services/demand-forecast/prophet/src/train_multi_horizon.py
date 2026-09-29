import json
import pickle
import mlflow
import holidays
import numpy as np
import pandas as pd
from prophet import Prophet
from prophet.serialize import model_to_json
from xgboost import XGBRegressor

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

from src.ensemble import weighted_ensemble
from src.multi_horizon import load_ensemble_weights, prepare_history
from src.multi_horizon_config import (
    MODEL_DIR,
    PROPHET_MODEL_PATH,
    XGB_MODEL_PATH,
    XGB_PARAMS,
    HORIZONS,
    INTERVALS_PATH,
    BACKTEST_CUTOFFS,
    BACKTEST_STEP_DAYS,
    BACKTEST_RESULTS_PATH,
    MLFLOW_EXPERIMENT,
    MIN_TRAINING_DAYS,
    INTERVAL_QUANTILES,
    PROPHET_PARAMS,
)
from src.multi_horizon_data import load_daily_data

from src.multi_horizon_inference import (
    create_daily_features,
    FEATURES,
    DATE_COLUMN,
    TARGET_COLUMN,
    predict_future_xgboost,
)


_US_HOLIDAYS = holidays.US()


def train_prophet_daily(df):
    """
    Train the daily Prophet model using
    the complete available history.
    """

    print(
        "\n========== Training Daily Prophet =========="
    )

    df = df.copy()

    feature_df = create_daily_features(
        df,
        drop_missing=False,
    )

    model = Prophet(
        **PROPHET_PARAMS,
    )

    model.add_regressor(
        "is_holiday"
    )

    training_columns = [
        DATE_COLUMN,
        TARGET_COLUMN,
        "is_holiday",
    ]

    prophet_df = feature_df[
        training_columns
    ].copy()

    prophet_df = prophet_df.rename(
        columns={
            DATE_COLUMN: "ds",
            TARGET_COLUMN: "y",
        }
    )

    model.fit(
        prophet_df
    )

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        PROPHET_MODEL_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            model_to_json(model)
        )

    print(
        "Daily Prophet saved:",
        PROPHET_MODEL_PATH,
    )

    return model

def fit_xgboost(df):
    """
    Fit the daily XGBoost model and return the inference package.

    This function does not save files. It is reusable by tests and
    training workflows.
    """

    df = prepare_history(df)

    feature_df = create_daily_features(
        df.rename(
            columns={
                "ds": "date",
                "y": "quantity_sold",
            }
        ),
        drop_missing=True,
    )

    if feature_df.empty:
        raise ValueError(
            "Not enough history to create XGBoost features."
        )

    X = feature_df[FEATURES]
    y = feature_df[TARGET_COLUMN]

    model = XGBRegressor(
        **XGB_PARAMS
    )

    model.fit(X, y)

    train_predictions = model.predict(X)

    residuals = (
        y.to_numpy() - train_predictions
    )

    residual_std = float(
        np.std(residuals)
    )

    return {
        "model": model,
        "features": FEATURES,
        "residual_std": residual_std,
    }
def train_xgboost_daily(df):
    """
    Train and persist the daily XGBoost model.
    """

    print(
        "\n========== Training Daily XGBoost=========="
    )

    feature_df = create_daily_features(
        df,
        drop_missing=True,
    )

    if feature_df.empty:
        raise ValueError(
            "Not enough history to create XGBoost features."
        )

    print(
        "XGBoost feature rows:",
        len(feature_df),
    )

    package = fit_xgboost(df)

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        XGB_MODEL_PATH,
        "wb",
    ) as file:

        pickle.dump(
            package,
            file,
        )

    print(
        "Daily XGBoost saved:",
        XGB_MODEL_PATH,
    )

    return package
def evaluate_xgboost_daily(
    df,
    test_days=90,
):
    """
    Optional chronological evaluation.

    This evaluation does not affect the final
    full-history model used for forecasting.
    """

    print(
        "\n========== Daily XGBoost Evaluation =========="
    )

    df = df.copy()

    feature_df = create_daily_features(
        df,
        drop_missing=True,
    )

    if len(feature_df) <= test_days:
        print(
            "Not enough rows for evaluation."
        )
        return None

    train = feature_df.iloc[
        :-test_days
    ].copy()

    test = feature_df.iloc[
        -test_days:
    ].copy()

    model = XGBRegressor(
        **XGB_PARAMS
    )

    model.fit(
        train[FEATURES],
        train[TARGET_COLUMN],
    )

    predictions = model.predict(
        test[FEATURES]
    )

    mae = mean_absolute_error(
        test[TARGET_COLUMN],
        predictions,
    )

    rmse = np.sqrt(
        mean_squared_error(
            test[TARGET_COLUMN],
            predictions,
        )
    )

    r2 = r2_score(
        test[TARGET_COLUMN],
        predictions,
    )

    print(
        f"Evaluation days: {test_days}"
    )

    print(
        f"MAE : {mae:.2f}"
    )

    print(
        f"RMSE: {rmse:.2f}"
    )

    print(
        f"R2  : {r2:.4f}"
    )

    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "r2": float(r2),
    }


def _train_backtest_prophet(train_df):
    """
    Train a fresh Prophet model for one rolling-origin
    backtest cutoff.
    """

    feature_df = create_daily_features(
        train_df,
        drop_missing=False,
    )

    model = Prophet(
        **PROPHET_PARAMS,
    )

    model.add_regressor(
        "is_holiday"
    )

    prophet_df = feature_df[
        [
            DATE_COLUMN,
            TARGET_COLUMN,
            "is_holiday",
        ]
    ].copy()

    prophet_df = prophet_df.rename(
        columns={
            DATE_COLUMN: "ds",
            TARGET_COLUMN: "y",
        }
    )

    model.fit(
        prophet_df
    )

    return model


def _forecast_backtest_prophet(
    model,
    train_df,
    horizon_days,
):
    """
    Forecast future daily demand from a backtest cutoff.
    """

    future = pd.DataFrame(
        {
            "ds": pd.date_range(
                start=(
                    train_df[DATE_COLUMN].max()
                    + pd.Timedelta(days=1)
                ),
                periods=horizon_days,
                freq="D",
            )
        }
    )

    future["is_holiday"] = (
        future["ds"]
        .dt.date
        .map(
            lambda d: int(
                d in _US_HOLIDAYS
            )
        )
    )

    forecast = model.predict(
        future
    )

    return np.maximum(
        0.0,
        forecast["yhat"].to_numpy(
            dtype=float
        ),
    )


def _train_backtest_xgboost(train_df):
    """
    Train a fresh XGBoost model for one rolling-origin
    backtest cutoff.
    """

    feature_df = create_daily_features(
        train_df,
        drop_missing=True,
    )

    if feature_df.empty:
        raise ValueError(
            "Not enough history to train XGBoost "
            "during interval calibration."
        )

    model = XGBRegressor(
        **XGB_PARAMS
    )

    model.fit(
        feature_df[FEATURES],
        feature_df[TARGET_COLUMN],
    )

    return {
        "model": model,
        "features": FEATURES,
        "residual_std": 0.0,
    }


def summarise_backtest(backtest: pd.DataFrame) -> dict:
    """
    Turn per-cutoff backtest results into honest metrics and intervals.

    `backtest` has one row per (cutoff, horizon) with columns
    horizon, actual, predicted.

    For each horizon:
      - mape: mean(|actual - predicted| / actual) * 100, a real MAPE.
      - bias_pct: mean((actual - predicted) / predicted) * 100.
      - low/high: multipliers from the INTERVAL_QUANTILES of the SIGNED
        error (actual / predicted - 1). With (0.10, 0.90) this is a real
        80% interval, and it can be asymmetric. The multipliers are
        widened to include 1.0 so the interval always contains the
        prediction.
      - coverage: share of backtest totals inside the interval. It is
        measured on the same errors used to calibrate, so it is
        optimistic; it is a sanity check, not a validation score.

    Intervals are NOT forced to be equal across horizons: each horizon
    is calibrated on its own errors.
    """

    low_q, high_q = INTERVAL_QUANTILES
    coverage_pct = round((high_q - low_q) * 100)

    ratio_quantiles = {}
    metrics = {}

    for horizon_name in HORIZONS:
        rows = backtest[backtest["horizon"] == horizon_name]

        if len(rows) < 3:
            raise ValueError(
                f"Not enough calibration observations "
                f"for {horizon_name}: {len(rows)}"
            )

        actual = rows["actual"].to_numpy(dtype=float)
        predicted = rows["predicted"].to_numpy(dtype=float)
        signed_error = actual / predicted - 1.0

        low = max(0.0, min(1.0, 1.0 + float(np.quantile(signed_error, low_q))))
        high = max(1.0, 1.0 + float(np.quantile(signed_error, high_q)))

        inside = (actual >= predicted * low) & (actual <= predicted * high)

        ratio_quantiles[horizon_name] = {
            "low": round(low, 6),
            "high": round(high, 6),
        }

        metrics[horizon_name] = {
            "mape": round(float(np.mean(np.abs(actual - predicted) / actual)) * 100, 2),
            "bias_pct": round(float(np.mean(signed_error)) * 100, 2),
            "coverage": round(float(np.mean(inside)), 3),
            "observations": int(len(rows)),
        }

    return {
        "interval_label": f"{coverage_pct}% empirical interval",
        "ratio_quantiles": ratio_quantiles,
        "backtest_metrics": metrics,
        "quantiles": {
            "low": low_q,
            "high": high_q,
        },
    }


def calibrate_horizon_intervals(df):
    """
    Calibrate empirical prediction intervals using
    rolling-origin backtesting.

    Cutoffs are anchored at the END of the data and step backwards, so
    the most recent behaviour is always included. Each cutoff:

      1. Trains fresh Prophet and XGBoost models on data before it.
      2. Forecasts the next 90 days (recursively, like production).
      3. Builds 1/7/30/90-day totals and records actual vs predicted.

    summarise_backtest() then turns those records into per-horizon
    MAPE, bias, coverage and interval multipliers.
    """

    print(
        "\n========== Horizon Interval Calibration =========="
    )

    df = (
        df.copy()
        .sort_values(DATE_COLUMN)
        .reset_index(drop=True)
    )

    total_rows = len(df)
    max_forecast_days = max(HORIZONS.values())
    required_rows = MIN_TRAINING_DAYS + max_forecast_days

    if total_rows < required_rows:
        raise ValueError(
            f"Not enough rows for interval calibration. "
            f"Need at least {required_rows}, got {total_rows}."
        )

    weights = load_ensemble_weights()

    # Latest possible cutoff first, then step backwards.
    cutoff_positions = []
    position = total_rows - max_forecast_days

    while (
        position >= MIN_TRAINING_DAYS
        and len(cutoff_positions) < BACKTEST_CUTOFFS
    ):
        cutoff_positions.append(position)
        position -= BACKTEST_STEP_DAYS

    cutoff_positions.sort()

    if not cutoff_positions:
        raise ValueError(
            "No valid rolling-origin backtest cutoffs available."
        )

    print(
        "Backtest cutoffs:",
        len(cutoff_positions),
    )

    records = []

    for cycle, cutoff_position in enumerate(
        cutoff_positions,
        start=1,
    ):
        train_df = df.iloc[:cutoff_position].copy()
        test_df = df.iloc[
            cutoff_position:
            cutoff_position + max_forecast_days
        ].copy()

        print(
            f"Backtest {cycle}/{len(cutoff_positions)} "
            f"(cutoff {train_df[DATE_COLUMN].max().date()})"
        )

        prophet_predictions = _forecast_backtest_prophet(
            _train_backtest_prophet(train_df),
            train_df,
            max_forecast_days,
        )

        xgb_forecast = predict_future_xgboost(
            model_info=_train_backtest_xgboost(train_df),
            history_df=train_df,
            horizon_days=max_forecast_days,
        )

        xgb_predictions = np.asarray(
            [float(row["prediction"]) for row in xgb_forecast],
            dtype=float,
        )

        if len(prophet_predictions) != max_forecast_days:
            raise ValueError(
                "Prophet backtest forecast length mismatch."
            )

        if len(xgb_predictions) != max_forecast_days:
            raise ValueError(
                "XGBoost backtest forecast length mismatch."
            )

        ensemble_predictions = np.asarray(
            [
                weighted_ensemble(
                    p,
                    x,
                    weights["prophet"],
                    weights["xgb"],
                )
                for p, x in zip(prophet_predictions, xgb_predictions)
            ],
            dtype=float,
        )

        actual_values = test_df[TARGET_COLUMN].to_numpy(dtype=float)

        for horizon_name, horizon_days in HORIZONS.items():
            predicted_total = float(np.sum(ensemble_predictions[:horizon_days]))
            actual_total = float(np.sum(actual_values[:horizon_days]))

            if predicted_total <= 0 or actual_total <= 0:
                continue

            records.append(
                {
                    "cutoff": str(train_df[DATE_COLUMN].max().date()),
                    "horizon": horizon_name,
                    "actual": actual_total,
                    "predicted": predicted_total,
                }
            )

    backtest = pd.DataFrame(records)
    calibration = summarise_backtest(backtest)

    calibration.update(
        {
            "backtest_cutoffs": len(cutoff_positions),
            "backtest_step_days": BACKTEST_STEP_DAYS,
            "min_training_days": MIN_TRAINING_DAYS,
            "first_cutoff": backtest["cutoff"].min(),
            "last_cutoff": backtest["cutoff"].max(),
        }
    )

    for horizon_name, m in calibration["backtest_metrics"].items():
        q = calibration["ratio_quantiles"][horizon_name]
        print(
            f"{horizon_name}: MAPE={m['mape']:.2f}%, "
            f"bias={m['bias_pct']:+.2f}%, "
            f"interval=[{q['low']:.4f}, {q['high']:.4f}], "
            f"coverage={m['coverage']:.0%}"
        )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    backtest.to_csv(BACKTEST_RESULTS_PATH, index=False)

    with INTERVALS_PATH.open("w", encoding="utf-8") as file:
        json.dump(calibration, file, indent=2)

    print(
        "\nHorizon interval calibration saved:",
        INTERVALS_PATH,
    )

    return calibration

def log_training_run(calibration: dict, weights: dict, n_rows: int) -> None:
    """
    Log the multi-horizon training run to MLflow: parameters,
    per-horizon backtest metrics, and every model/calibration artifact.

    Must be called inside an active MLflow run.
    """

    mlflow.log_params(
        {
            **{f"xgb_{k}": v for k, v in XGB_PARAMS.items()},
            **{f"prophet_{k}": v for k, v in PROPHET_PARAMS.items()},
            "weight_prophet": weights["prophet"],
            "weight_xgb": weights["xgb"],
            "backtest_cutoffs": calibration["backtest_cutoffs"],
            "backtest_step_days": BACKTEST_STEP_DAYS,
            "min_training_days": MIN_TRAINING_DAYS,
            "interval_quantiles": str(INTERVAL_QUANTILES),
            "training_rows": n_rows,
        }
    )

    for horizon_name, m in calibration["backtest_metrics"].items():
        mlflow.log_metrics(
            {
                f"{horizon_name}_mape": m["mape"],
                f"{horizon_name}_bias_pct": m["bias_pct"],
                f"{horizon_name}_interval_coverage": m["coverage"],
            }
        )

    for path in (
        PROPHET_MODEL_PATH,
        XGB_MODEL_PATH,
        INTERVALS_PATH,
        BACKTEST_RESULTS_PATH,
    ):
        mlflow.log_artifact(str(path), artifact_path="multi_horizon")


def train_all():
    """
    Train both daily models, calibrate empirical multi-horizon
    intervals, and log everything to MLflow.
    """

    df = load_daily_data()

    print("\nDataset:")
    print(f"Rows : {len(df)}")
    print(f"Start: {df[DATE_COLUMN].min().date()}")
    print(f"End  : {df[DATE_COLUMN].max().date()}")

    mlflow.set_experiment(MLFLOW_EXPERIMENT)

    with mlflow.start_run(run_name="multi_horizon_training"):
        evaluate_xgboost_daily(
            df,
            test_days=90,
        )

        prophet_model = train_prophet_daily(df)
        xgb_package = train_xgboost_daily(df)
        calibration = calibrate_horizon_intervals(df)

        log_training_run(
            calibration,
            load_ensemble_weights(),
            len(df),
        )

    print("\n========================================")
    print("Daily multi-horizon models trained.")
    print("Horizon intervals calibrated and logged to MLflow.")
    print("========================================")

    return {
        "prophet": prophet_model,
        "xgb": xgb_package,
        "interval_calibration": calibration,
    }

if __name__ == "__main__":
    train_all()