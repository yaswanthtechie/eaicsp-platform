

import numpy as np
import pandas as pd


DATE_COLUMN = "ds"
TARGET_COLUMN = "y"


FEATURES = [
    "lag_1",
    "lag_7",
    "lag_30",
    "rolling_mean_7",
    "rolling_mean_30",
    "rolling_std_7",
    "is_holiday",
    "day_of_week",
    "month",
    "quarter",
    "year"
]


def create_features(df, drop_missing=True):
    """
    Create lag, rolling and calendar features.

    drop_missing=True  -> Training
    drop_missing=False -> Future Forecast
    """

    df = df.copy()

    df[DATE_COLUMN] = pd.to_datetime(
        df[DATE_COLUMN]
    )

    df = df.sort_values(
        DATE_COLUMN
    )

    # Lag Features

    df["lag_1"] = (
        df[TARGET_COLUMN]
        .shift(1)
    )

    df["lag_7"] = (
        df[TARGET_COLUMN]
        .shift(7)
    )

    df["lag_30"] = (
        df[TARGET_COLUMN]
        .shift(30)
    )

    # Rolling Features

    df["rolling_mean_7"] = (
        df[TARGET_COLUMN]
        .shift(1)
        .rolling(7)
        .mean()
    )

    df["rolling_mean_30"] = (
        df[TARGET_COLUMN]
        .shift(1)
        .rolling(30)
        .mean()
    )

    df["rolling_std_7"] = (
        df[TARGET_COLUMN]
        .shift(1)
        .rolling(7)
        .std()
    )

    # Holiday Feature

    df["is_holiday"] = (

        df[DATE_COLUMN]
        .dt.month
        .isin([11, 12])

        |

        df[DATE_COLUMN]
        .dt.day
        .isin([1, 25])

    ).astype(int)

    # Calendar Features

    df["day_of_week"] = (
        df[DATE_COLUMN]
        .dt.dayofweek
    )

    df["month"] = (
        df[DATE_COLUMN]
        .dt.month
    )

    df["quarter"] = (
        df[DATE_COLUMN]
        .dt.quarter
    )

    df["year"] = (
        df[DATE_COLUMN]
        .dt.year
    )

    if drop_missing:
        df = df.dropna()

    return df


def predict_xgboost(model_info, df):
    """
    Prediction on existing dataframe.
    Used for evaluation.
    """

    model = model_info["model"]

    residual_std = model_info["residual_std"]

    features = model_info["features"]

    feature_df = create_features(
        df,
        drop_missing=True
    )

    X = feature_df[features]

    predictions = model.predict(
        X
    )

    interval = (
        1.96 *
        residual_std
    )

    result = feature_df.copy()

    result["prediction"] = predictions

    result["lower"] = (
        predictions -
        interval
    )

    result["upper"] = (
        predictions +
        interval
    )

    return (
        predictions,
        result
    )


def predict_future_xgboost(
    model_info,
    history_df,
    horizon_months
):
    """
    Generate future monthly demand forecasts recursively using XGBoost.

    The function predicts one future month at a time. After each prediction,
    the predicted demand is added to the historical data and is then used
    when generating features for the next forecast month.

    This recursive approach allows lag and rolling features to be generated
    for future periods even though the actual future demand is unknown.

    Missing feature values in future rows are handled as follows:
    1. Forward-fill (ffill) uses the most recently available feature value.
    2. Any remaining NaN values are replaced with 0.

    Prediction intervals are calculated using the model's training residual
    standard deviation and a 95% confidence multiplier of 1.96.

    Example:
        If the latest historical month is 2025-12 and horizon_months=3:

            2025-12 historical demand
                    ↓
            Predict 2026-01
                    ↓
            Add 2026-01 prediction to history
                    ↓
            Predict 2026-02
                    ↓
            Add 2026-02 prediction to history
                    ↓
            Predict 2026-03

    Args:
        model_info: Dictionary containing the trained XGBoost model,
            feature names, and training residual standard deviation.
        history_df: Historical demand DataFrame containing `ds` and `y`
            columns.
        horizon_months: Number of future months to forecast.

    Returns:
        A list of dictionaries containing the forecast date, prediction,
        lower prediction bound, and upper prediction bound.
    """

    model = model_info["model"]

    residual_std = model_info["residual_std"]

    features = model_info["features"]

    history = history_df.copy()

    history["ds"] = pd.to_datetime(
        history["ds"]
    )

    forecasts = []

    for _ in range(horizon_months):

        next_date = (
            history["ds"].max()
            +
            pd.DateOffset(
                months=1
            )
        )

        history = pd.concat(
            [
                history,
                pd.DataFrame({
                    "ds": [
                        next_date
                    ],
                    "y": [
                        np.nan
                    ]
                })
            ],
            ignore_index=True
        )

        feature_df = create_features(
            history,
            drop_missing=False
        )

        latest = feature_df.tail(
            1
        ).copy()

        latest[features] = (
            latest[features]
            .ffill()
            .fillna(0)
        )

        prediction = model.predict(
            latest[features]
        )[0]

        history.loc[
            history.index[-1],
            "y"
        ] = prediction

        interval = (
            1.96 *
            residual_std
        )

        forecasts.append({

            "date": next_date.strftime(
                "%Y-%m-%d"
            ),

            "prediction": float(
                prediction
            ),

            "lower": float(
                prediction -
                interval
            ),

            "upper": float(
                prediction +
                interval
            )

        })

    return forecasts