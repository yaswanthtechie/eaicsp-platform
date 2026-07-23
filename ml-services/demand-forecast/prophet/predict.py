from prophet import Prophet
from src.data import load_sales_data


def predict(horizon_months: int) -> dict:
    # Load data
    df = load_sales_data()

    # Prophet column names
    prophet_df = df.rename(columns={
        "date": "ds",
        "quantity_sold": "y"
    })

    # Train model on all available data
    model = Prophet()
    model.fit(prophet_df)

    # Future dates
    future = model.make_future_dataframe(
        periods=horizon_months,
        freq="MS"
    )

    forecast = model.predict(future)

    # Keep only future predictions
    future_forecast = forecast.tail(horizon_months)

    result = {
        "forecast": []
    }

    for _, row in future_forecast.iterrows():
        result["forecast"].append({
            "date": row["ds"].strftime("%Y-%m-%d"),
            "predicted": round(row["yhat"], 2),
            "lower": round(row["yhat_lower"], 2),
            "upper": round(row["yhat_upper"], 2)
        })

    return result