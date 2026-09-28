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
from src.multi_horizon import prepare_history
from src.multi_horizon_config import (
    MODEL_DIR,
    PROPHET_MODEL_PATH,
    XGB_MODEL_PATH,
    XGB_PARAMS,
    HORIZONS,
    INTERVALS_PATH,
    BACKTEST_CUTOFFS,
    BACKTEST_STEP_DAYS,
    MIN_TRAINING_DAYS,
    INTERVAL_QUANTILES,
    PROPHET_PARAMS,
    WEIGHTS_PATH,
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


def calibrate_horizon_intervals(df):
    """
    Calibrate empirical prediction intervals using
    rolling-origin backtesting.

    Each cutoff:

      1. Trains fresh Prophet and XGBoost models.
      2. Forecasts the next 90 days.
      3. Builds 1/7/30/90-day totals.
      4. Calculates absolute relative error for each horizon.
      5. Uses the empirical upper error quantile.
      6. Converts the error into prediction-centered
         lower and upper multipliers.
      7. Prevents uncertainty from shrinking as the
         forecast horizon increases.

    The calibrated multipliers are saved to
    horizon_intervals.json and later used by
    src.multi_horizon.py.
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

    required_rows = (
        MIN_TRAINING_DAYS
        + max(HORIZONS.values())
    )

    if total_rows < required_rows:
        raise ValueError(
            f"Not enough rows for interval calibration. "
            f"Need at least {required_rows}, got {total_rows}."
        )

    if not WEIGHTS_PATH.exists():
        raise FileNotFoundError(
            f"Ensemble weights not found: {WEIGHTS_PATH}"
        )

    with WEIGHTS_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        weight_data = json.load(file)

    prophet_weight = float(
        weight_data["prophet"]
    )

    xgb_weight = float(
        weight_data["xgb"]
    )

    weights_total = (
        prophet_weight
        + xgb_weight
    )

    if not np.isfinite(
        prophet_weight
    ) or not np.isfinite(
        xgb_weight
    ):
        raise ValueError(
            "Ensemble weights must be finite."
        )

    if prophet_weight < 0 or xgb_weight < 0:
        raise ValueError(
            "Ensemble weights must be non-negative."
        )

    if not np.isclose(
        weights_total,
        1.0,
    ):
        raise ValueError(
            f"Ensemble weights must sum to 1.0, "
            f"got {weights_total}"
        )

    # Store absolute relative errors rather than
    # actual/predicted ratios.
    errors = {
        horizon_name: []
        for horizon_name in HORIZONS
    }

    max_forecast_days = max(
        HORIZONS.values()
    )

    max_cutoff = (
        total_rows
        - max_forecast_days
    )

    cutoff_positions = []

    position = MIN_TRAINING_DAYS

    while (
        position <= max_cutoff
        and len(cutoff_positions)
        < BACKTEST_CUTOFFS
    ):
        cutoff_positions.append(
            position
        )

        position += (
            BACKTEST_STEP_DAYS
        )

    if not cutoff_positions:
        raise ValueError(
            "No valid rolling-origin backtest cutoffs available."
        )

    print(
        "Backtest cutoffs:",
        len(cutoff_positions),
    )

    for cycle, cutoff_position in enumerate(
        cutoff_positions,
        start=1,
    ):
        print(
            f"\nBacktest "
            f"{cycle}/{len(cutoff_positions)}"
        )

        train_df = df.iloc[
            :cutoff_position
        ].copy()

        test_df = df.iloc[
            cutoff_position:
            cutoff_position + max_forecast_days
        ].copy()

        if len(test_df) < max_forecast_days:
            continue

        # ----------------------------------------------
        # Train fresh Prophet
        # ----------------------------------------------

        prophet_model = (
            _train_backtest_prophet(
                train_df
            )
        )

        prophet_predictions = (
            _forecast_backtest_prophet(
                prophet_model,
                train_df,
                max_forecast_days,
            )
        )

        # ----------------------------------------------
        # Train fresh XGBoost
        # ----------------------------------------------

        xgb_package = (
            _train_backtest_xgboost(
                train_df
            )
        )

        xgb_forecast = (
            predict_future_xgboost(
                model_info=xgb_package,
                history_df=train_df,
                horizon_days=max_forecast_days,
            )
        )

        xgb_predictions = np.asarray(
            [
                float(row["prediction"])
                for row in xgb_forecast
            ],
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

        # ----------------------------------------------
        # Ensemble forecast
        # ----------------------------------------------

        ensemble_predictions = np.asarray(
            [
                weighted_ensemble(
                    prophet_prediction,
                    xgb_prediction,
                    prophet_weight,
                    xgb_weight,
                )
                for prophet_prediction, xgb_prediction
                in zip(
                    prophet_predictions,
                    xgb_predictions,
                )
            ],
            dtype=float,
        )

        actual_values = test_df[
            TARGET_COLUMN
        ].to_numpy(
            dtype=float
        )

        # ----------------------------------------------
        # Calculate horizon relative errors
        # ----------------------------------------------

        for horizon_name, horizon_days in HORIZONS.items():

            predicted_total = float(
                np.sum(
                    ensemble_predictions[
                        :horizon_days
                    ]
                )
            )

            actual_total = float(
                np.sum(
                    actual_values[
                        :horizon_days
                    ]
                )
            )

            if predicted_total <= 0:
                continue

            relative_error = (
                abs(
                    actual_total
                    - predicted_total
                )
                / predicted_total
            )

            if not np.isfinite(
                relative_error
            ):
                continue

            errors[
                horizon_name
            ].append(
                float(relative_error)
            )

    # ----------------------------------------------
    # Empirical error quantiles
    # ----------------------------------------------

    ratio_quantiles = {}

    _, high_quantile = (
        INTERVAL_QUANTILES
    )

    previous_error = 0.0

    for horizon_name in HORIZONS:

        values = np.asarray(
            errors[horizon_name],
            dtype=float,
        )

        if len(values) < 3:
            raise ValueError(
                f"Not enough calibration observations "
                f"for {horizon_name}: {len(values)}"
            )

        error_quantile = float(
            np.quantile(
                values,
                high_quantile,
            )
        )

        # Do not allow interval uncertainty
        # to shrink at a longer horizon.
        error_quantile = max(
            previous_error,
            error_quantile,
        )

        previous_error = error_quantile

        low = max(
            0.0,
            1.0 - error_quantile,
        )

        high = 1.0 + error_quantile

        ratio_quantiles[
            horizon_name
        ] = {
            "low": round(
                low,
                6,
            ),
            "high": round(
                high,
                6,
            ),
        }

        print(
            f"{horizon_name}: "
            f"observations={len(values)}, "
            f"error={error_quantile:.6f}, "
            f"low={low:.6f}, "
            f"high={high:.6f}"
        )

    calibration = {
        "interval_label": (
            "80% empirical interval"
        ),
        "ratio_quantiles": ratio_quantiles,
        "backtest_cutoffs": len(
            cutoff_positions
        ),
        "backtest_step_days": (
            BACKTEST_STEP_DAYS
        ),
        "min_training_days": (
            MIN_TRAINING_DAYS
        ),
        "quantiles": {
            "low": INTERVAL_QUANTILES[0],
            "high": INTERVAL_QUANTILES[1],
        },
    }

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with INTERVALS_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            calibration,
            file,
            indent=2,
        )

    print(
        "\nHorizon interval calibration saved:",
        INTERVALS_PATH,
    )

    return calibration


def train_all():
    """
    Train both daily models and calibrate
    empirical multi-horizon intervals.
    """

    df = load_daily_data()

    print(
        "\nDataset:"
    )

    print(
        f"Rows : {len(df)}"
    )

    print(
        f"Start: {df[DATE_COLUMN].min().date()}"
    )

    print(
        f"End  : {df[DATE_COLUMN].max().date()}"
    )

    evaluate_xgboost_daily(
        df,
        test_days=90,
    )

    prophet_model = train_prophet_daily(
        df
    )

    xgb_package = train_xgboost_daily(
        df
    )

    calibration = calibrate_horizon_intervals(
        df
    )

    print(
        "\n========================================"
    )

    print(
        "Daily multi-horizon models trained."
    )

    print(
        "Horizon intervals calibrated."
    )

    print(
        "========================================"
    )

    return {
        "prophet": prophet_model,
        "xgb": xgb_package,
        "interval_calibration": calibration,
    }


if __name__ == "__main__":
    train_all()