import os
import pandas as pd
from src.make_messy_data import generate_messy_data


def test_generate_messy_data(tmp_path):
    """
    Tests that the data generator creates the correct file structure
    and injects the exact number of expected errors based on the fixed seed.
    """
    # 1. SETUP: Define a temporary file path that automatically cleans up after the test
    test_filepath = tmp_path / "test_messy_sales.csv"

    # 2. EXECUTE: Run the generator targeting the temporary path
    generate_messy_data(filepath=str(test_filepath))

    # 3. ASSERT: File creation
    assert test_filepath.exists(), "The CSV file was not created."

    # 4. ASSERT: Data structure and exact error counts
    df = pd.read_csv(test_filepath)

    # Total rows: 970 base + 30 duplicates = 1000
    assert len(df) == 1000, f"Expected 1000 rows, got {len(df)}"
    assert list(df.columns) == ["date", "product_name", "quantity_sold"]

    # Check for exactly 12 unparseable dates
    invalid_dates_count = (df["date"] == "invalid_date").sum()
    assert invalid_dates_count == 12, f"Expected 12 invalid dates, got {invalid_dates_count}"

    # Check for exactly 47 missing quantities
    missing_qty_count = df["quantity_sold"].isna().sum()
    assert missing_qty_count == 47, f"Expected 47 missing quantities, got {missing_qty_count}"

    # Check for exactly 6 negative quantities
    # (Pandas safely evaluates NaNs as False in < comparisons)
    negative_qty_count = (df["quantity_sold"] < 0).sum()
    assert negative_qty_count == 6, f"Expected 6 negative quantities, got {negative_qty_count}"

    # Check for exactly 45 duplicated rows
    # (30 injected system duplicates + 15 organic duplicates naturally occurring in the random data)
    duplicate_count = df.duplicated(keep="first").sum()
    assert duplicate_count == 45, f"Expected 45 exact duplicates, got {duplicate_count}"