"""Build data/m5_daily_sales.csv (total daily units) from the raw M5 files.

Download sales_train_validation.csv and calendar.csv from Kaggle
(M5 Forecasting - Accuracy) into data/raw/ first.
"""

import pandas as pd

from src.multi_horizon_config import DATA_PATH, RAW_DATA_DIR


def main() -> None:
    sales = pd.read_csv(RAW_DATA_DIR / "sales_train_validation.csv")
    calendar = pd.read_csv(RAW_DATA_DIR / "calendar.csv", usecols=["d", "date"])

    day_columns = [c for c in sales.columns if c.startswith("d_")]
    totals = (
        sales[day_columns]
        .sum()
        .rename_axis("d")
        .reset_index(name="quantity_sold")
    )

    daily = (
        totals.merge(calendar, on="d", how="left", validate="one_to_one")
        [["date", "quantity_sold"]]
        .sort_values("date")
    )
    if daily["date"].isna().any():
        raise ValueError("Some M5 day columns have no calendar date.")

    daily.to_csv(DATA_PATH, index=False)
    print(f"Wrote {len(daily)} rows to {DATA_PATH}")


if __name__ == "__main__":
    main()