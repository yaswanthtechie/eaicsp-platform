import pandas as pd
from prophet import Prophet


def forecast_sku_demand(
    hierarchy_df: pd.DataFrame,
    forecast_date: str,
) -> pd.DataFrame:
    """
    Generate one actual model forecast for every SKU.

    Historical data:
        date, sku_id, category, region, quantity_sold

    Output:
        date, sku_id, predicted
    """

    required_columns = {
        "date",
        "sku_id",
        "category",
        "region",
        "quantity_sold",
    }

    missing = required_columns - set(hierarchy_df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    df = hierarchy_df.copy()

    df["date"] = pd.to_datetime(df["date"])
    df["quantity_sold"] = pd.to_numeric(
        df["quantity_sold"],
        errors="raise",
    )

    forecast_date = pd.Timestamp(forecast_date)

    results = []

    for sku_id, sku_df in df.groupby("sku_id"):

        sku_df = sku_df.sort_values("date")

        # Only historical data before forecast date
        train_df = sku_df[
            sku_df["date"] < forecast_date
        ].copy()

        if len(train_df) < 2:
            raise ValueError(
                f"Not enough history for SKU {sku_id}"
            )

        # Prophet format
        prophet_df = train_df[
            ["date", "quantity_sold"]
        ].rename(
            columns={
                "date": "ds",
                "quantity_sold": "y",
            }
        )

        # Actual forecasting model
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
        )

        model.fit(prophet_df)

        future = pd.DataFrame(
            {
                "ds": [forecast_date]
            }
        )

        prediction = model.predict(future)

        predicted = float(
            prediction.iloc[0]["yhat"]
        )

        # Demand cannot be negative
        predicted = max(0.0, predicted)

        results.append(
            {
                "date": forecast_date,
                "sku_id": sku_id,
                "predicted": round(
                    predicted,
                    2,
                ),
            }
        )

    return pd.DataFrame(results)