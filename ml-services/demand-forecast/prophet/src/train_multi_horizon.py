
import json
import pickle

import mlflow
import holidays
import numpy as np
import pandas as pd

from pathlib import Path

from prophet import Prophet
from prophet.serialize import model_to_json
from xgboost import XGBRegressor

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

from src.ensemble import weighted_ensemble

from src.conformal import (
    evaluate_interval_methods,
    calibration_radius,
)

from src.multi_horizon import (
    load_ensemble_weights,
    prepare_history,
)

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
    CALIBRATION_CUTOFFS,
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
        80% interval, and it can be asymmetric.
      - coverage: share of backtest totals inside the interval. It is
        measured on the same errors used to calibrate, so it is
        optimistic; it is a sanity check, not a validation score.

    Intervals are NOT forced to be equal across horizons: each horizon
    is calibrated on its own errors.
    """

    low_q, high_q = INTERVAL_QUANTILES

    coverage_pct = round(
        (high_q - low_q) * 100
    )

    ratio_quantiles = {}
    metrics = {}

    for horizon_name in HORIZONS:

        rows = backtest[
            backtest["horizon"] == horizon_name
        ]

        if len(rows) < 3:
            raise ValueError(
                f"Not enough calibration observations "
                f"for {horizon_name}: {len(rows)}"
            )

        actual = rows[
            "actual"
        ].to_numpy(dtype=float)

        predicted = rows[
            "predicted"
        ].to_numpy(dtype=float)

        signed_error = (
            actual / predicted - 1.0
        )

        low = max(
            0.0,
            min(
                1.0,
                1.0
                + float(
                    np.quantile(
                        signed_error,
                        low_q,
                    )
                ),
            ),
        )

        high = max(
            1.0,
            1.0
            + float(
                np.quantile(
                    signed_error,
                    high_q,
                )
            ),
        )

        inside = (
            (actual >= predicted * low)
            & (actual <= predicted * high)
        )

        ratio_quantiles[
            horizon_name
        ] = {
            "low": round(low, 6),
            "high": round(high, 6),
        }

        metrics[
            horizon_name
        ] = {
            "mape": round(
                float(
                    np.mean(
                        np.abs(actual - predicted)
                        / actual
                    )
                )
                * 100,
                2,
            ),
            "bias_pct": round(
                float(
                    np.mean(
                        signed_error
                    )
                )
                * 100,
                2,
            ),
            "coverage": round(
                float(
                    np.mean(inside)
                ),
                3,
            ),
            "observations": int(
                len(rows)
            ),
        }

    return {
        "interval_label": (
            f"{coverage_pct}% empirical interval"
        ),
        "ratio_quantiles": ratio_quantiles,
        "backtest_metrics": metrics,
        "quantiles": {
            "low": low_q,
            "high": high_q,
        },
    }


def _split_backtest_calibration_evaluation(
    backtest: pd.DataFrame,
    calibration_cutoffs: int,
    gap_days: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split rolling-origin backtest results chronologically.

    Earlier cutoff windows are used only for calibration.

    Later cutoff windows are kept completely held out for
    interval coverage evaluation.

    `gap_days` prevents calibration and evaluation forecast
    windows from overlapping.

    For example, when the longest forecast horizon is 90 days,
    the first evaluation cutoff must be at least 90 days after
    the last calibration cutoff.
    """

    if calibration_cutoffs <= 0:
        raise ValueError(
            "calibration_cutoffs must be positive."
        )

    if gap_days < 0:
        raise ValueError(
            "gap_days cannot be negative."
        )

    if backtest.empty:
        raise ValueError(
            "backtest cannot be empty."
        )

    required_columns = {
        "cutoff",
        "horizon",
        "actual",
        "predicted",
    }

    missing = (
        required_columns
        - set(backtest.columns)
    )

    if missing:
        raise ValueError(
            f"backtest missing required columns: "
            f"{sorted(missing)}"
        )

    cutoffs = sorted(
        backtest["cutoff"].unique()
    )

    if len(cutoffs) <= calibration_cutoffs:
        raise ValueError(
            "Not enough cutoff windows for a separate "
            "calibration and held-out evaluation period."
        )

    calibration_cutoff_values = cutoffs[
        :calibration_cutoffs
    ]

    evaluation_cutoff_values = cutoffs[
        calibration_cutoffs:
    ]

    # ---------------------------------------------------------
    # Fix 5:
    # Prevent calibration and evaluation forecast windows
    # from overlapping.
    # ---------------------------------------------------------
    if gap_days > 0:

        first_allowed = (
            pd.Timestamp(
                calibration_cutoff_values[-1]
            )
            + pd.Timedelta(
                days=gap_days
            )
        )

        evaluation_cutoff_values = [
            cutoff
            for cutoff in evaluation_cutoff_values
            if pd.Timestamp(cutoff)
            >= first_allowed
        ]

    if not evaluation_cutoff_values:
        raise ValueError(
            "No held-out evaluation cutoffs remain after "
            "the gap. Lower calibration_cutoffs or gap_days."
        )

    calibration = (
        backtest[
            backtest["cutoff"].isin(
                calibration_cutoff_values
            )
        ]
        .copy()
        .sort_values(
            ["cutoff", "horizon"]
        )
        .reset_index(drop=True)
    )

    evaluation = (
        backtest[
            backtest["cutoff"].isin(
                evaluation_cutoff_values
            )
        ]
        .copy()
        .sort_values(
            ["cutoff", "horizon"]
        )
        .reset_index(drop=True)
    )

    return calibration, evaluation


def log_training_run(
    calibration,
    weights,
    n_rows,
):
    """
    Log multi-horizon training results to MLflow.
    """

    import mlflow

    # =========================================================
    # Parameters
    # =========================================================

    mlflow.log_param(
        "n_rows",
        int(n_rows),
    )

    mlflow.log_param(
        "weight_prophet",
        float(weights["prophet"]),
    )

    mlflow.log_param(
        "weight_xgb",
        float(weights["xgb"]),
    )

    mlflow.log_param(
        "backtest_cutoffs",
        int(
            calibration.get(
                "backtest_cutoffs",
                0,
            )
        ),
    )

    mlflow.log_param(
        "backtest_step_days",
        int(
            calibration.get(
                "backtest_step_days",
                BACKTEST_STEP_DAYS,
            )
        ),
    )

    mlflow.log_param(
        "min_training_days",
        int(
            calibration.get(
                "min_training_days",
                MIN_TRAINING_DAYS,
            )
        ),
    )

    conformal_evaluation = calibration.get(
        "conformal_evaluation",
        {},
    )

    if conformal_evaluation:

        mlflow.log_param(
            "calibration_cutoffs",
            int(
                conformal_evaluation.get(
                    "calibration_cutoffs",
                    0,
                )
            ),
        )

        mlflow.log_param(
            "evaluation_cutoffs",
            int(
                conformal_evaluation.get(
                    "evaluation_cutoffs",
                    0,
                )
            ),
        )

    # =========================================================
    # Backtest metrics
    # =========================================================

    backtest_metrics = calibration.get(
        "backtest_metrics",
        {},
    )

    for horizon_name, metrics in (
        backtest_metrics.items()
    ):

        safe_name = horizon_name.replace(
            "-",
            "_",
        )

        if "mape" in metrics:
            mlflow.log_metric(
                f"{safe_name}_mape",
                float(metrics["mape"]),
            )

        if "bias_pct" in metrics:
            mlflow.log_metric(
                f"{safe_name}_bias_pct",
                float(metrics["bias_pct"]),
            )

        if "coverage" in metrics:
            mlflow.log_metric(
                f"{safe_name}_interval_coverage",
                float(metrics["coverage"]),
            )

    # =========================================================
    # Conformal before / after metrics
    # =========================================================

    conformal_results = (
        conformal_evaluation.get(
            "results",
            {},
        )
    )

    for horizon_name, horizon_results in (
        conformal_results.items()
    ):

        safe_horizon = horizon_name.replace(
            "-",
            "_",
        )

        for coverage_name, result in (
            horizon_results.items()
        ):

            safe_coverage = (
                coverage_name.replace(
                    "%",
                    "",
                )
            )

            before = result.get(
                "before",
                {},
            )

            after = result.get(
                "after",
                {},
            )

            if "coverage" in before:
                mlflow.log_metric(
                    (
                        f"{safe_horizon}_"
                        f"before_coverage_"
                        f"{safe_coverage}"
                    ),
                    float(
                        before["coverage"]
                    ),
                )

            if "coverage" in after:
                mlflow.log_metric(
                    (
                        f"{safe_horizon}_"
                        f"after_coverage_"
                        f"{safe_coverage}"
                    ),
                    float(
                        after["coverage"]
                    ),
                )

            if "pinball_loss" in before:
                mlflow.log_metric(
                    (
                        f"{safe_horizon}_"
                        f"before_pinball_"
                        f"{safe_coverage}"
                    ),
                    float(
                        before["pinball_loss"]
                    ),
                )

            if "pinball_loss" in after:
                mlflow.log_metric(
                    (
                        f"{safe_horizon}_"
                        f"after_pinball_"
                        f"{safe_coverage}"
                    ),
                    float(
                        after["pinball_loss"]
                    ),
                )

            if "calibration_radius" in result:
                mlflow.log_metric(
                    (
                        f"{safe_horizon}_"
                        f"conformal_radius_"
                        f"{safe_coverage}"
                    ),
                    float(
                        result[
                            "calibration_radius"
                        ]
                    ),
                )

    # =========================================================
    # Artifacts
    # =========================================================

    artifact_paths = [
        PROPHET_MODEL_PATH,
        XGB_MODEL_PATH,
        INTERVALS_PATH,
        BACKTEST_RESULTS_PATH,
    ]

    for artifact_path in artifact_paths:

        artifact_path = Path(
            artifact_path
        )

        if artifact_path.exists():

            mlflow.log_artifact(
                str(artifact_path),
                artifact_path="multi_horizon",
            )


def calibrate_horizon_intervals(df):
    """
    Calibrate multi-horizon prediction intervals using
    chronological rolling-origin backtesting.

    Backtest windows are split chronologically:

        earlier cutoffs -> calibration
        later cutoffs   -> held-out evaluation

    A gap equal to the longest forecast horizon is placed
    between calibration and evaluation cutoffs so that their
    forecast windows cannot overlap.

    Calibration data is used to estimate:
      - existing empirical intervals
      - split-conformal intervals

    Held-out evaluation data is used only to measure:
      - before coverage
      - after coverage
      - before pinball loss
      - after pinball loss

    Horizons:
      - 1 day
      - 7 days
      - 30 days
      - 90 days

    Coverage targets:
      - 80%
      - 95%
    """

    print(
        "\n========== Horizon Interval Calibration =========="
    )

    # ---------------------------------------------------------
    # 1. Prepare data
    # ---------------------------------------------------------

    df = (
        df.copy()
        .sort_values(DATE_COLUMN)
        .reset_index(drop=True)
    )

    total_rows = len(df)

    max_forecast_days = max(
        HORIZONS.values()
    )

    required_rows = (
        MIN_TRAINING_DAYS
        + max_forecast_days
    )

    if total_rows < required_rows:
        raise ValueError(
            f"Not enough rows for interval calibration. "
            f"Need at least {required_rows}, "
            f"got {total_rows}."
        )

    weights = load_ensemble_weights()

    # ---------------------------------------------------------
    # 2. Build chronological rolling-origin cutoffs
    # ---------------------------------------------------------

    cutoff_positions = []

    position = (
        total_rows
        - max_forecast_days
    )

    while (
        position >= MIN_TRAINING_DAYS
        and len(cutoff_positions)
        < BACKTEST_CUTOFFS
    ):

        cutoff_positions.append(
            position
        )

        position -= (
            BACKTEST_STEP_DAYS
        )

    cutoff_positions.sort()

    if not cutoff_positions:
        raise ValueError(
            "No valid rolling-origin backtest "
            "cutoffs available."
        )

    if len(cutoff_positions) <= CALIBRATION_CUTOFFS:
        raise ValueError(
            "Not enough backtest cutoffs for a separate "
            "calibration and held-out evaluation period. "
            f"Got {len(cutoff_positions)} cutoffs, "
            f"but CALIBRATION_CUTOFFS="
            f"{CALIBRATION_CUTOFFS}."
        )

    print(
        "Backtest cutoffs:",
        len(cutoff_positions),
    )

    print(
        "Calibration cutoffs:",
        CALIBRATION_CUTOFFS,
    )

    # Fix 5:
    # The actual number of held-out evaluation cutoffs
    # is determined after applying the gap.
    expected_evaluation_cutoffs = max(
        0,
        len(cutoff_positions)
        - CALIBRATION_CUTOFFS,
    )

    print(
        "Potential evaluation cutoffs:",
        expected_evaluation_cutoffs,
    )

    print(
        "Evaluation gap days:",
        max_forecast_days,
    )

    # ---------------------------------------------------------
    # 3. Rolling-origin backtest
    # ---------------------------------------------------------

    records = []

    for cycle, cutoff_position in enumerate(
        cutoff_positions,
        start=1,
    ):

        train_df = (
            df.iloc[:cutoff_position]
            .copy()
        )

        test_df = (
            df.iloc[
                cutoff_position:
                cutoff_position + max_forecast_days
            ]
            .copy()
        )

        cutoff_date = (
            train_df[DATE_COLUMN]
            .max()
            .date()
        )

        print(
            f"Backtest {cycle}/"
            f"{len(cutoff_positions)} "
            f"(cutoff {cutoff_date})"
        )

        # -----------------------------------------------------
        # Prophet
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # XGBoost
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # Validate forecast lengths
        # -----------------------------------------------------

        if len(prophet_predictions) != max_forecast_days:
            raise ValueError(
                "Prophet backtest forecast "
                "length mismatch."
            )

        if len(xgb_predictions) != max_forecast_days:
            raise ValueError(
                "XGBoost backtest forecast "
                "length mismatch."
            )

        # -----------------------------------------------------
        # Ensemble prediction
        # -----------------------------------------------------

        ensemble_predictions = np.asarray(
            [
                weighted_ensemble(
                    prophet_prediction,
                    xgb_prediction,
                    weights["prophet"],
                    weights["xgb"],
                )
                for prophet_prediction, xgb_prediction
                in zip(
                    prophet_predictions,
                    xgb_predictions,
                )
            ],
            dtype=float,
        )

        actual_values = (
            test_df[TARGET_COLUMN]
            .to_numpy(dtype=float)
        )

        if len(actual_values) < max_forecast_days:
            raise ValueError(
                "Backtest test window is shorter "
                "than the maximum forecast horizon."
            )

        # -----------------------------------------------------
        # 4. Build horizon totals
        # -----------------------------------------------------

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

            if (
                predicted_total <= 0
                or actual_total <= 0
            ):
                continue

            records.append(
                {
                    "cutoff": str(cutoff_date),
                    "horizon": horizon_name,
                    "actual": actual_total,
                    "predicted": predicted_total,
                }
            )

    # ---------------------------------------------------------
    # 5. Convert backtest records to DataFrame
    # ---------------------------------------------------------

    backtest = pd.DataFrame(
        records
    )

    if backtest.empty:
        raise ValueError(
            "Rolling-origin backtest produced "
            "no valid records."
        )

    # ---------------------------------------------------------
    # 6. Split calibration vs held-out evaluation
    # ---------------------------------------------------------

    calibration_df, evaluation_df = (
        _split_backtest_calibration_evaluation(
            backtest,
            calibration_cutoffs=CALIBRATION_CUTOFFS,
            gap_days=max_forecast_days,
        )
    )

    evaluation_cutoff_count = int(
        evaluation_df["cutoff"].nunique()
    )

    print(
        "\nCalibration rows:",
        len(calibration_df),
    )

    print(
        "Held-out evaluation rows:",
        len(evaluation_df),
    )

    print(
        "Held-out evaluation cutoffs:",
        evaluation_cutoff_count,
    )

    # ---------------------------------------------------------
    # 7. Existing empirical calibration
    #
    # Keep this because production currently depends on
    # ratio_quantiles.
    #
    # IMPORTANT:
    # These values are now calculated ONLY from the
    # calibration period, not the held-out period.
    # ---------------------------------------------------------

    calibration = summarise_backtest(
        calibration_df
    )

    # ---------------------------------------------------------
    # 8. Conformal evaluation
    # ---------------------------------------------------------

    conformal_evaluation = {}

    for horizon_name in HORIZONS:

        calibration_rows = (
            calibration_df[
                calibration_df["horizon"]
                == horizon_name
            ]
        )

        evaluation_rows = (
            evaluation_df[
                evaluation_df["horizon"]
                == horizon_name
            ]
        )

        if calibration_rows.empty:
            raise ValueError(
                f"No calibration rows for "
                f"{horizon_name}."
            )

        if evaluation_rows.empty:
            raise ValueError(
                f"No held-out evaluation rows "
                f"for {horizon_name}."
            )

        horizon_results = {}

        # -----------------------------------------------------
        # 80% and 95% intervals
        # -----------------------------------------------------

        for coverage in (
            0.80,
            0.95,
        ):

            result = evaluate_interval_methods(
                calibration_actual=(
                    calibration_rows[
                        "actual"
                    ].to_numpy(dtype=float)
                ),
                calibration_predicted=(
                    calibration_rows[
                        "predicted"
                    ].to_numpy(dtype=float)
                ),
                evaluation_actual=(
                    evaluation_rows[
                        "actual"
                    ].to_numpy(dtype=float)
                ),
                evaluation_predicted=(
                    evaluation_rows[
                        "predicted"
                    ].to_numpy(dtype=float)
                ),
                coverage=coverage,
            )

            horizon_results[
                f"{int(coverage * 100)}%"
            ] = result

        conformal_evaluation[
            horizon_name
        ] = horizon_results

    # ---------------------------------------------------------
    # 9. Print before vs after results
    # ---------------------------------------------------------

    print(
        "\n========== Conformal Evaluation "
        "on Held-out Windows =========="
    )

    for horizon_name, results in (
        conformal_evaluation.items()
    ):

        print(
            f"\n{horizon_name}"
        )

        for coverage, result in (
            results.items()
        ):

            print(
                f"  {coverage}: "
                f"before coverage="
                f"{result['before']['coverage']:.3f}, "
                f"after coverage="
                f"{result['after']['coverage']:.3f}, "
                f"before pinball="
                f"{result['before']['pinball_loss']:.2f}, "
                f"after pinball="
                f"{result['after']['pinball_loss']:.2f}, "
                f"conformal radius="
                f"{result['calibration_radius']:.4f}"
            )
        # ---------------------------------------------------------
    # 9b. Final served conformal intervals.
    # The held-out evaluation above is finished, so the radius
    # used in production is re-fit on ALL backtest windows.
    # ---------------------------------------------------------
    conformal_intervals = {}

    for horizon_name in HORIZONS:
        rows = backtest[backtest["horizon"] == horizon_name]
        conformal_intervals[horizon_name] = {}

        for coverage in (0.80, 0.95):
            radius = calibration_radius(
                rows["actual"].to_numpy(dtype=float),
                rows["predicted"].to_numpy(dtype=float),
                coverage,
            )

            conformal_intervals[horizon_name][f"{round(coverage * 100)}%"] = {
                "low": round(max(0.0, 1.0 - radius), 6),
                "high": round(1.0 + radius, 6),
            }

    calibration["conformal_intervals"] = conformal_intervals        

    # ---------------------------------------------------------
    # 10. Save M1 evaluation metadata
    # ---------------------------------------------------------

    calibration[
        "conformal_evaluation"
    ] = {
        "calibration_cutoffs": (
            CALIBRATION_CUTOFFS
        ),
        "evaluation_cutoffs": (
            evaluation_cutoff_count
        ),
        "gap_days": int(
            max_forecast_days
        ),
        "results": conformal_evaluation,
    }

    calibration[
        "backtest_cutoffs"
    ] = len(cutoff_positions)

    calibration[
        "backtest_step_days"
    ] = BACKTEST_STEP_DAYS

    calibration[
        "min_training_days"
    ] = MIN_TRAINING_DAYS

    calibration[
        "first_cutoff"
    ] = backtest["cutoff"].min()

    calibration[
        "last_cutoff"
    ] = backtest["cutoff"].max()

    # ---------------------------------------------------------
    # 11. Print existing calibration metrics
    # ---------------------------------------------------------

    print(
        "\n========== Calibration Metrics =========="
    )

    for horizon_name, metrics in (
        calibration[
            "backtest_metrics"
        ].items()
    ):

        quantiles = (
            calibration[
                "ratio_quantiles"
            ][horizon_name]
        )

        print(
            f"{horizon_name}: "
            f"MAPE={metrics['mape']:.2f}%, "
            f"bias={metrics['bias_pct']:+.2f}%, "
            f"interval="
            f"[{quantiles['low']:.4f}, "
            f"{quantiles['high']:.4f}], "
            f"calibration coverage="
            f"{metrics['coverage']:.0%}"
        )

    # ---------------------------------------------------------
    # 12. Save backtest results
    # ---------------------------------------------------------

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    backtest.to_csv(
        BACKTEST_RESULTS_PATH,
        index=False,
    )

    # ---------------------------------------------------------
    # 13. Save calibration JSON
    # ---------------------------------------------------------

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
    Train both daily models, calibrate multi-horizon intervals
    (empirical + split-conformal), and log everything to MLflow.
    """

    df = load_daily_data()

    print("\nDataset:")
    print(
        f"Rows : {len(df)}"
    )
    print(
        f"Start: {df[DATE_COLUMN].min().date()}"
    )
    print(
        f"End  : {df[DATE_COLUMN].max().date()}"
    )

    mlflow.set_experiment(
        MLFLOW_EXPERIMENT
    )

    with mlflow.start_run(
        run_name="multi_horizon_training"
    ):

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

        log_training_run(
            calibration,
            load_ensemble_weights(),
            len(df),
        )

    print(
        "\n========================================"
    )

    print(
        "Daily multi-horizon models trained."
    )

    print(
        "Horizon intervals calibrated and logged to MLflow."
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
