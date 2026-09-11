# train_prophet.py

import os
import pandas as pd
from prophet import Prophet
from prophet.serialize import model_to_json


def train_prophet(train_df):
    """
    Train Prophet model and save it.
    """

    print("Training Prophet model...")

    df = train_df.copy()

    # Rename columns if required
    if "date" in df.columns:
        df = df.rename(columns={"date": "ds"})

    if "demand" in df.columns:
        df = df.rename(columns={"demand": "y"})

    # Validate columns
    required_columns = ["ds", "y"]

    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    df["ds"] = pd.to_datetime(df["ds"])

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False
    )

    model.fit(df[["ds", "y"]])

    # Create output folder
    os.makedirs("output", exist_ok=True)

    # Save model
    with open("output/prophet_model.json", "w") as f:
        f.write(model_to_json(model))

    print(" Prophet model trained successfully.")
    print(" Prophet model saved: output/prophet_model.json")

    return model


def predict_prophet(model, test_df):
    """
    Generate Prophet forecast.
    Returns complete forecast needed for evaluation,
    plotting and prediction intervals.
    """

    print("\n========== Running Prophet Prediction ==========")

    df = test_df.copy()

    if df.empty:
        raise ValueError("Test dataframe is empty.")

    # Rename if necessary
    if "ds" not in df.columns:

        if "date" in df.columns:
            df = df.rename(columns={"date": "ds"})
        else:
            raise ValueError("Missing 'ds' column.")

    df["ds"] = pd.to_datetime(df["ds"])

    future_df = df[["ds"]]

    print("Future dataframe:", future_df.shape)

    forecast = model.predict(future_df)

    # Return only required columns
    forecast = forecast[
        [
            "ds",
            "yhat",
            "yhat_lower",
            "yhat_upper"
        ]
    ].copy()

    return forecast