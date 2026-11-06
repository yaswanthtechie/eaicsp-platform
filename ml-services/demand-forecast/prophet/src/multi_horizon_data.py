import numpy as np
import pandas as pd

from src.seed_demand import aggregate_daily, load_seed_sales


def load_daily_data():
    """
    Load total daily demand across all canonical SKU/warehouse pairs
        in the R15 seed (data-platform/out/sales_daily.csv, written by `make seed`).
    Returns
    -------
    pandas.DataFrame
        DataFrame with:
        - date
        - quantity_sold
    """

    df = aggregate_daily(load_seed_sales())

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

    df["date"] = pd.to_datetime(
        df["date"]
    )

    df["quantity_sold"] = pd.to_numeric(
        df["quantity_sold"],
        errors="coerce",
    )

    df = df.sort_values(
        "date"
    ).reset_index(drop=True)

    if df.empty:
        raise ValueError(
            "Daily dataset is empty."
        )

    if df["date"].duplicated().any():
        raise ValueError(
            "Duplicate dates found."
        )

    if df["date"].isna().any():
        raise ValueError(
            "Missing dates found."
        )

    if df["quantity_sold"].isna().any():
        raise ValueError(
            "Missing demand values found."
        )

    if not np.isfinite(
        df["quantity_sold"]
    ).all():
        raise ValueError(
            "Demand contains non-finite values."
        )

    if (df["quantity_sold"] < 0).any():
        raise ValueError(
            "Negative demand found."
        )

    expected_dates = pd.date_range(
        start=df["date"].min(),
        end=df["date"].max(),
        freq="D",
    )

    actual_dates = pd.DatetimeIndex(
        df["date"]
    )

    if not actual_dates.equals(
        expected_dates
    ):
        raise ValueError(
            "Daily dataset contains date gaps."
        )

    return df