from prophet import Prophet
from prophet.serialize import model_to_json
import os


def train_prophet(train_df):
    """
    Train Prophet model and save it.
    """

    # Validate required columns
    required_columns = ["ds", "y"]

    for column in required_columns:
        if column not in train_df.columns:
            raise ValueError(f"Missing required column: {column}")

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False
    )

    print("Training Prophet model...")

    # Train model
    model.fit(train_df)

    # Create output folder if it doesn't exist
    os.makedirs("output", exist_ok=True)

    # Save trained model
    with open("output/prophet_model.json", "w") as f:
        f.write(model_to_json(model))

    print(" Prophet model saved: output/prophet_model.json")

    return model


def predict_prophet(model, future_df):
    """
    Predict using trained Prophet model.
    """

    if "ds" not in future_df.columns:
        raise ValueError("Future dataframe must contain 'ds' column.")

    forecast = model.predict(
        future_df[["ds"]]
    )

    return forecast["yhat"].values