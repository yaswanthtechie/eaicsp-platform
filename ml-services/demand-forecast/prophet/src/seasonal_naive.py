import pandas as pd


def seasonal_naive_forecast(
    train_df: pd.DataFrame,
    horizon_months: int,
    season_length: int = 12,
) -> list:
    """
    Seasonal Naive baseline for monthly demand.

    Each future month's prediction is taken from
    the same month in the previous year.

    Example:

        2015-01 -> 2016-01 prediction
        2015-02 -> 2016-02 prediction
        ...
        2015-12 -> 2016-12 prediction
    """

    # ----------------------------------------
    # Validate input
    # ----------------------------------------

    if train_df.empty:
        raise ValueError(
            "Training data cannot be empty."
        )

    if horizon_months <= 0:
        raise ValueError(
            "horizon_months must be greater than 0."
        )

    required_columns = [
        "ds",
        "y",
    ]

    for column in required_columns:

        if column not in train_df.columns:

            raise ValueError(
                f"Missing required column: {column}"
            )

    # ----------------------------------------
    # Prepare data
    # ----------------------------------------

    df = train_df.copy()

    df["ds"] = pd.to_datetime(
        df["ds"]
    )

    df = df.sort_values(
        "ds"
    ).reset_index(drop=True)

    # ----------------------------------------
    # Validate demand
    # ----------------------------------------

    if df["y"].isna().any():

        raise ValueError(
            "Missing demand values found."
        )

    # ----------------------------------------
    # Validate seasonal history
    # ----------------------------------------

    if len(df) < season_length:

        raise ValueError(
            "Not enough history for seasonal naive forecast."
        )

    # ----------------------------------------
    # Generate forecast
    # ----------------------------------------

    forecasts = []

    history = df.copy()

    for _ in range(horizon_months):

        # Next month
        next_date = (
            history["ds"].max()
            + pd.DateOffset(months=1)
        )

        # Same month previous year
        seasonal_date = (
            next_date
            - pd.DateOffset(
                months=season_length
            )
        )

        # Find previous year's same month
        matching_rows = history[
            history["ds"] == seasonal_date
        ]

        if matching_rows.empty:

            raise ValueError(
                "No seasonal history found for "
                f"{seasonal_date.strftime('%Y-%m-%d')}"
            )

        prediction = float(
            matching_rows.iloc[0]["y"]
        )

        forecasts.append(
            {
                "date": next_date.strftime(
                    "%Y-%m-%d"
                ),
                "prediction": prediction,
            }
        )

        # Add predicted value to history
        # so recursive forecasting can continue.
        history = pd.concat(
            [
                history,
                pd.DataFrame(
                    {
                        "ds": [next_date],
                        "y": [prediction],
                    }
                ),
            ],
            ignore_index=True,
        )

    return forecasts