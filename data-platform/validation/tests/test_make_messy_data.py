import pandas as pd
from src.make_messy_data import generate_messy_data, MessyDataConfig


def test_generate_messy_data(tmp_path):
    """
    Tests that the data generator creates the correct file structure,
    returns a DataFrame, and injects the expected dynamic percentage of errors
    matching the sales_fact schema.
    """
    # 1. SETUP: Define a temporary file path
    test_filepath = tmp_path / "test_messy_sales.csv"
    n_base = 970

    # Initialize the configuration dataclass
    config = MessyDataConfig(n_base=n_base)

    # 2. EXECUTE: Run the generator targeting the temporary path with the config
    df_returned = generate_messy_data(filepath=str(test_filepath), config=config)

    # 3. ASSERT: File creation and Return Type
    assert test_filepath.exists(), "The CSV file was not created."
    assert isinstance(df_returned, pd.DataFrame), "Function did not return a pandas DataFrame."

    # 4. ASSERT: Data structure
    df = pd.read_csv(test_filepath)

    # Calculate the dynamic injected values based on the config object attributes
    expected_system_dupes = int(n_base * config.frac_exact_duplicates)  # ~30
    expected_min_missing_date = int(n_base * config.frac_missing_date)  # ~11
    expected_min_missing_qty = int(n_base * config.frac_missing_qty)  # ~48
    expected_min_neg_qty = int(n_base * config.frac_negative_qty)  # ~5
    expected_min_bad_sku = int(n_base * config.frac_bad_sku_format)  # ~14
    expected_min_missing_sku = int(n_base * config.frac_missing_sku)  # ~9
    expected_min_missing_price = int(n_base * config.frac_missing_price)  # ~19

    # Total rows: 970 base + 30 duplicates = 1000
    expected_total_rows = n_base + expected_system_dupes
    assert len(df) == expected_total_rows, f"Expected {expected_total_rows} rows, got {len(df)}"

    # Assert the new schema columns map perfectly to sales_fact
    assert list(df.columns) == ["date", "sku_id", "warehouse_id", "quantity_sold", "unit_price"]

    # Check for missing dates
    missing_dates_count = df["date"].isna().sum()
    assert missing_dates_count >= expected_min_missing_date, f"Expected >= {expected_min_missing_date} missing dates, got {missing_dates_count}"

    # Check for missing quantities
    missing_qty_count = df["quantity_sold"].isna().sum()
    assert missing_qty_count >= expected_min_missing_qty, f"Expected >= {expected_min_missing_qty} missing quantities, got {missing_qty_count}"

    # Check for negative quantities
    negative_qty_count = (df["quantity_sold"] < 0).sum()
    assert negative_qty_count >= expected_min_neg_qty, f"Expected >= {expected_min_neg_qty} negative quantities, got {negative_qty_count}"

    # Check for bad SKUs dynamically using the config string
    bad_sku_count = (df["sku_id"] == config.bad_sku_string).sum()
    assert bad_sku_count >= expected_min_bad_sku, f"Expected >= {expected_min_bad_sku} bad SKUs, got {bad_sku_count}"

    # Check for missing SKUs
    missing_sku_count = df["sku_id"].isna().sum()
    assert missing_sku_count >= expected_min_missing_sku, f"Expected >= {expected_min_missing_sku} missing SKUs, got {missing_sku_count}"

    # Check for missing Prices
    missing_price_count = df["unit_price"].isna().sum()
    assert missing_price_count >= expected_min_missing_price, f"Expected >= {expected_min_missing_price} missing prices, got {missing_price_count}"

    # Check for duplicated rows
    # (Total duplicates = injected system duplicates + naturally occurring organic duplicates)
    duplicate_count = df.duplicated(keep="first").sum()
    assert duplicate_count >= expected_system_dupes, f"Expected >= {expected_system_dupes} exact duplicates, got {duplicate_count}"