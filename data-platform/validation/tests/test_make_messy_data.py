import pandas as pd

from src.make_messy_data import generate_messy_data


def test_generate_messy_data(tmp_path):
    """
    Tests that the data generator creates the correct file structure,
    returns a DataFrame, and injects the expected dynamic percentage of errors.
    """
    # 1. SETUP: Define a temporary file path
    test_filepath = tmp_path / "test_messy_sales.csv"
    n_base = 970

    # 2. EXECUTE: Run the generator targeting the temporary path
    # The updated function now returns the DataFrame directly
    df_returned = generate_messy_data(filepath=str(test_filepath), n_base=n_base)

    # 3. ASSERT: File creation and Return Type
    assert test_filepath.exists(), "The CSV file was not created."
    assert isinstance(df_returned, pd.DataFrame), "Function did not return a pandas DataFrame."

    # 4. ASSERT: Data structure
    df = pd.read_csv(test_filepath)

    # Calculate the dynamic injected values based on the updated script logic
    expected_system_dupes = int(n_base * 0.031)  # 30
    expected_min_invalid = int(n_base * 0.012)  # 11
    expected_min_missing = int(n_base * 0.05)  # 48
    expected_min_neg = int(n_base * 0.006)  # 5

    # Total rows: 970 base + 30 duplicates = 1000
    expected_total_rows = n_base + expected_system_dupes
    assert len(df) == expected_total_rows, f"Expected {expected_total_rows} rows, got {len(df)}"
    assert list(df.columns) == ["date", "product_name", "quantity_sold"]

    # Check for unparseable dates (Using >= because a bad date row might have been duplicated)
    invalid_dates_count = (df["date"] == "invalid_date").sum()
    assert invalid_dates_count >= expected_min_invalid, f"Expected at least {expected_min_invalid} invalid dates, got {invalid_dates_count}"

    # Check for missing quantities
    missing_qty_count = df["quantity_sold"].isna().sum()
    assert missing_qty_count >= expected_min_missing, f"Expected at least {expected_min_missing} missing quantities, got {missing_qty_count}"

    # Check for negative quantities
    negative_qty_count = (df["quantity_sold"] < 0).sum()
    assert negative_qty_count >= expected_min_neg, f"Expected at least {expected_min_neg} negative quantities, got {negative_qty_count}"

    # Check for duplicated rows
    # (Total duplicates = injected system duplicates + naturally occurring organic duplicates)
    duplicate_count = df.duplicated(keep="first").sum()
    assert duplicate_count >= expected_system_dupes, f"Expected at least {expected_system_dupes} exact duplicates, got {duplicate_count}"