"""
External Regressors for Demand Forecasting.

Creates external signals used by forecasting models:

- Holiday indicator
- Promotion indicator
- Mock weather index
"""

import numpy as np
import pandas as pd


def add_external_regressors(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add external forecasting regressors.

    Parameters
    ----------
    df : pd.DataFrame
        Sales dataframe containing:
        - date
        - quantity_sold

    Returns
    -------
    pd.DataFrame
        Dataset with external regressors.
    """

    data = df.copy()

    data["date"] = pd.to_datetime(data["date"])

    # ==========================================
    # Holiday Feature
    # ==========================================

    holiday_months = [11, 12]

    data["is_holiday"] = (
        data["date"].dt.month.isin(holiday_months)
    ).astype(int)

    # ==========================================
    # Promotion Feature
    # ==========================================

    promotion_months = [3, 6, 9, 12]

    data["promotion"] = (
        data["date"].dt.month.isin(promotion_months)
    ).astype(int)

    # ==========================================
    # Mock Weather Feature
    # ==========================================

    np.random.seed(42)

    data["weather_index"] = np.random.uniform(
        0.0,
        1.0,
        len(data),
    )

    return data


def validate_external_regressors(
    df: pd.DataFrame,
) -> None:
    """
    Validate external regressor columns.
    """

    required_columns = [
        "is_holiday",
        "promotion",
        "weather_index",
    ]

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing external regressors: {missing}"
        )

    if not df["is_holiday"].isin([0, 1]).all():
        raise ValueError(
            "is_holiday must contain only 0 or 1."
        )

    if not df["promotion"].isin([0, 1]).all():
        raise ValueError(
            "promotion must contain only 0 or 1."
        )

    if (
        (df["weather_index"] < 0).any()
        or
        (df["weather_index"] > 1).any()
    ):
        raise ValueError(
            "weather_index must be between 0 and 1."
        )


if __name__ == "__main__":

    from src.data import load_sales_data

    df = load_sales_data()

    df = add_external_regressors(df)

    validate_external_regressors(df)

    print(
        df[
            [
                "date",
                "quantity_sold",
                "is_holiday",
                "promotion",
                "weather_index",
            ]
        ].head(10)
    )

    print("\nExternal regressors added successfully.")