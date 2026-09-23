# train_prophet.py

import os

import pandas as pd

from prophet import Prophet
from prophet.serialize import model_to_json


# External regressors used by Prophet
EXTERNAL_REGRESSORS = [
    "is_holiday",
    "promotion",
    "weather_index",
]


def train_prophet(train_df):
    """
    Train Prophet model with external regressors
    and save it.
    """

    print("Training Prophet model...")

    df = train_df.copy()

    # Rename columns if required
    if "date" in df.columns:
        df = df.rename(columns={"date": "ds"})

    if "demand" in df.columns:
        df = df.rename(columns={"demand": "y"})

    # Validate required columns
    required_columns = [
        "ds",
        "y",
        *EXTERNAL_REGRESSORS,
    ]

    for col in required_columns:

        if col not in df.columns:
            raise ValueError(
                f"Missing required column: {col}"
            )

    df["ds"] = pd.to_datetime(df["ds"])

    # ==========================================
    # Create Prophet Model
    # ==========================================

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
    )

    # ==========================================
    # Add External Regressors
    # ==========================================

    for regressor in EXTERNAL_REGRESSORS:

        model.add_regressor(
            regressor
        )

    print(
        "External regressors added to Prophet:"
    )

    for regressor in EXTERNAL_REGRESSORS:

        print(
            f" - {regressor}"
        )

    # ==========================================
    # Train Model
    # ==========================================

    training_columns = [
        "ds",
        "y",
        *EXTERNAL_REGRESSORS,
    ]

    model.fit(
        df[training_columns]
    )

    # ==========================================
    # Save Model
    # ==========================================

    os.makedirs(
        "output",
        exist_ok=True,
    )

    with open(
        "output/prophet_model.json",
        "w",
    ) as f:

        f.write(
            model_to_json(model)
        )

    print(
        "Prophet model trained successfully."
    )

    print(
        "Prophet model saved: output/prophet_model.json"
    )

    return model


def predict_prophet(model, test_df):
    """
    Generate Prophet forecast using
    external regressors.

    Returns forecast required for:
    - evaluation
    - plotting
    - prediction intervals
    """

    print(
        "\n========== Running Prophet Prediction =========="
    )

    df = test_df.copy()

    if df.empty:

        raise ValueError(
            "Test dataframe is empty."
        )

    # ==========================================
    # Rename Date Column
    # ==========================================

    if "ds" not in df.columns:

        if "date" in df.columns:

            df = df.rename(
                columns={"date": "ds"}
            )

        else:

            raise ValueError(
                "Missing 'ds' column."
            )

    df["ds"] = pd.to_datetime(
        df["ds"]
    )

    # ==========================================
    # Validate External Regressors
    # ==========================================

    for regressor in EXTERNAL_REGRESSORS:

        if regressor not in df.columns:

            raise ValueError(
                f"Missing external regressor: {regressor}"
            )

    # ==========================================
    # Create Future Dataframe
    # ==========================================

    future_columns = [
        "ds",
        *EXTERNAL_REGRESSORS,
    ]

    future_df = df[
        future_columns
    ].copy()

    print(
        "Future dataframe:",
        future_df.shape,
    )

    # ==========================================
    # Generate Forecast
    # ==========================================

    forecast = model.predict(
        future_df
    )

    # ==========================================
    # Return Required Columns
    # ==========================================

    forecast = forecast[
        [
            "ds",
            "yhat",
            "yhat_lower",
            "yhat_upper",
        ]
    ].copy()

    return forecast