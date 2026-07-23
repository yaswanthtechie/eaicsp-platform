import pandas as pd


URL = "https://raw.githubusercontent.com/facebook/prophet/main/examples/example_retail_sales.csv"


def load_sales_data() -> pd.DataFrame:
    """
    Load the sales dataset and rename columns.
    Returns columns: date, quantity_sold
    """
    df = pd.read_csv(URL)

    df = df.rename(
        columns={
            "ds": "date",
            "y": "quantity_sold"
        }
    )

    df["date"] = pd.to_datetime(df["date"])

    return df


def validate(df: pd.DataFrame) -> None:
    """
    Validate the dataset.
    Raises ValueError if validation fails.
    """

    # Missing dates
    if df["date"].isnull().any():
        raise ValueError("Missing dates found.")

    # Negative sales
    if (df["quantity_sold"] < 0).any():
        raise ValueError("Negative sales found.")

    # Duplicate dates
    if df["date"].duplicated().any():
        raise ValueError("Duplicate dates found.")