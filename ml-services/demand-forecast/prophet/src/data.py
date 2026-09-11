from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_PATH = PROJECT_ROOT / "data" / "retail_sales.csv"

# Upstream source of the vendored dataset above.
# Used only by refresh_sales_data(), never at predict time.
SOURCE_URL = (
    "https://raw.githubusercontent.com/facebook/prophet/"
    "main/examples/example_retail_sales.csv"
)


def load_sales_data() -> pd.DataFrame:
    """
    Load the sales dataset and rename columns.
    Returns columns: date, quantity_sold

    Reads the vendored CSV in data/ so that training and
    inference never depend on network access.
    """

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Sales dataset not found at {DATA_PATH}.\n"
            "Run: python -m src.data  (refreshes it from the upstream source)"
        )

    df = pd.read_csv(DATA_PATH)

    df = df.rename(
        columns={
            "ds": "date",
            "y": "quantity_sold"
        }
    )

    df["date"] = pd.to_datetime(df["date"])

    validate(df)

    return df


def refresh_sales_data() -> pd.DataFrame:
    """
    Re-download the dataset from the upstream source and
    overwrite the vendored copy in data/.

    This is a deliberate, manual step -- it is the only
    place in the project that touches the network.
    """

    df = pd.read_csv(SOURCE_URL)

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA_PATH, index=False)

    print(f"Refreshed {DATA_PATH} ({len(df)} rows) from {SOURCE_URL}")

    return df


def validate(df: pd.DataFrame) -> None:
    """
    Validate the dataset.
    Raises ValueError if validation fails.
    """

    if df["date"].isnull().any():
        raise ValueError("Missing dates found.")

    if (df["quantity_sold"] < 0).any():
        raise ValueError("Negative sales found.")

    if df["date"].duplicated().any():
        raise ValueError("Duplicate dates found.")

    print("Dataset validation passed.")


if __name__ == "__main__":
    refresh_sales_data()