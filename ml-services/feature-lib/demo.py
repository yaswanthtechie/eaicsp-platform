import pandas as pd

from src.build_features import build_all_features


URL = "https://raw.githubusercontent.com/facebook/prophet/main/examples/example_retail_sales.csv"


def main():

    # Load dataset
    df = pd.read_csv(URL)

    # Rename columns
    df = df.rename(
        columns={
            "ds": "date",
            "y": "quantity_sold"
        }
    )

    # Convert date column
    df["date"] = pd.to_datetime(df["date"])

    # Build all features
    result = build_all_features(
        df,
        date_col="date",
        target_col="quantity_sold"
    )

    # Show first 10 rows
    print(result.head(10))


if __name__ == "__main__":
    main()