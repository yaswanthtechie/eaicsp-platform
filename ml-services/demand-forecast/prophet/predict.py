from prophet.serialize import model_from_json


def predict(horizon_months: int) -> dict:
    """
    Load saved Prophet model and generate forecast.
    """

    # Load saved Prophet model
    with open("output/prophet_model.json", "r") as f:
        model = model_from_json(f.read())

    # Create future dates
    future = model.make_future_dataframe(
        periods=horizon_months,
        freq="MS"
    )

    # Predict
    forecast = model.predict(future)

    # Future predictions only
    future_forecast = forecast.tail(horizon_months)

    result = {
        "forecast": []
    }

    for _, row in future_forecast.iterrows():

        result["forecast"].append({
            "date": row["ds"].strftime("%Y-%m-%d"),
            "predicted": round(float(row["yhat"]), 2),
            "lower": round(float(row["yhat_lower"]), 2),
            "upper": round(float(row["yhat_upper"]), 2)
        })

    return result