import os
import pickle
from pathlib import Path

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

from src.inference import (
    create_features,
    FEATURES,
    DATE_COLUMN,
    TARGET_COLUMN,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "m5_daily_sales.csv"
)

MODEL_DIR = (
    PROJECT_ROOT
    / "models"
    / "multi_horizon"
)

PROPHET_MODEL_PATH = (
    MODEL_DIR
    / "prophet_daily.json"
)

XGB_MODEL_PATH = (
    MODEL_DIR
    / "xgb_daily.pkl"
)


EXTERNAL_REGRESSORS = [
    "is_holiday",
    "promotion",
    "weather_index",
]


XGB_PARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.03,
    "max_depth": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "objective": "reg:squarederror",
    "random_state": 42,
}


def load_daily_data():
    """
    Load the aggregated M5 daily demand dataset.
    """

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Daily M5 dataset not found: {DATA_PATH}"
        )

    df = pd.read_csv(
        DATA_PATH
    )

    required = [
        "date",
        "quantity_sold",
    ]

    missing = [
        col
        for col in required
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing columns: {missing}"
        )

    df = df.rename(
        columns={
            "date": "ds",
            "quantity_sold": "y",
        }
    )

    df["ds"] = pd.to_datetime(
        df["ds"]
    )

    df["y"] = pd.to_numeric(
        df["y"],
        errors="coerce",
    )

    df = df.sort_values(
        "ds"
    ).reset_index(drop=True)

    if df.empty:
        raise ValueError(
            "Daily dataset is empty."
        )

    if df["ds"].duplicated().any():
        raise ValueError(
            "Duplicate dates found."
        )

    if df["ds"].isna().any():
        raise ValueError(
            "Missing dates found."
        )

    if df["y"].isna().any():
        raise ValueError(
            "Missing demand values found."
        )

    if not np.isfinite(
        df["y"]
    ).all():
        raise ValueError(
            "Demand contains non-finite values."
        )

    if (df["y"] < 0).any():
        raise ValueError(
            "Negative demand found."
        )

    expected_dates = pd.date_range(
        start=df["ds"].min(),
        end=df["ds"].max(),
        freq="D",
    )

    actual_dates = pd.DatetimeIndex(
        df["ds"]
    )

    if not actual_dates.equals(
        expected_dates
    ):
        raise ValueError(
            "Daily dataset contains date gaps."
        )

    return df


def add_default_regressors(df):
    """
    Add Task 1 default regressors.

    These are placeholders for Task 1.
    Regressor ablation belongs to Task 2.
    """

    df = df.copy()

    if "is_holiday" not in df.columns:

        df["is_holiday"] = (
            df["ds"].dt.month.isin(
                [11, 12]
            )
            |
            df["ds"].dt.day.isin(
                [1, 25]
            )
        ).astype(int)

    if "promotion" not in df.columns:
        df["promotion"] = 0

    if "weather_index" not in df.columns:
        df["weather_index"] = 0.0

    return df


def train_prophet_daily(df):
    """
    Train the daily Prophet model using
    the complete available history.
    """

    print(
        "\n========== Training Daily Prophet =========="
    )

    df = df.copy()

    df = add_default_regressors(
        df
    )

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
    )

    for regressor in EXTERNAL_REGRESSORS:
        model.add_regressor(
            regressor
        )

    training_columns = [
        "ds",
        "y",
        *EXTERNAL_REGRESSORS,
    ]

    model.fit(
        df[training_columns]
    )

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        PROPHET_MODEL_PATH,
        "w",
    ) as file:

        file.write(
            model_to_json(model)
        )

    print(
        "Daily Prophet saved:",
        PROPHET_MODEL_PATH,
    )

    return model


def train_xgboost_daily(df):
    """
    Train the daily XGBoost model using
    the complete available history.

    The model is trained on historical lag
    and rolling features.
    """

    print(
        "\n========== Training Daily XGBoost =========="
    )

    df = df.copy()

    df = add_default_regressors(
        df
    )

    feature_df = create_features(
        df,
        drop_missing=True,
    )

    if feature_df.empty:
        raise ValueError(
            "Not enough history to create XGBoost features."
        )

    X = feature_df[
        FEATURES
    ]

    y = feature_df[
        TARGET_COLUMN
    ]

    print(
        "XGBoost feature rows:",
        len(feature_df),
    )

    model = XGBRegressor(
        **XGB_PARAMS
    )

    model.fit(
        X,
        y,
    )

    train_predictions = model.predict(
        X
    )

    residuals = (
        y.to_numpy()
        -
        train_predictions
    )

    residual_std = float(
        np.std(residuals)
    )

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    package = {
        "model": model,
        "features": FEATURES,
        "residual_std": residual_std,
    }

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

    print(
        "Residual std:",
        residual_std,
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

    df = add_default_regressors(
        df
    )

    feature_df = create_features(
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


def train_all():
    """
    Train both daily models.
    """

    df = load_daily_data()

    print(
        "\nDataset:"
    )

    print(
        f"Rows : {len(df)}"
    )

    print(
        f"Start: {df['ds'].min().date()}"
    )

    print(
        f"End  : {df['ds'].max().date()}"
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

    print(
        "\n========================================"
    )

    print(
        "Daily multi-horizon models trained."
    )

    print(
        "========================================"
    )

    return {
        "prophet": prophet_model,
        "xgb": xgb_package,
    }


if __name__ == "__main__":
    train_all()