import pandas as pd
from unittest.mock import patch
from src.make_messy_data import generate_messy_data, MessyDataConfig, main


def test_generate_messy_data(tmp_path):
    """
    Tests that the data generator creates the correct file structure,
    streams the output to disk (returns None), and injects the expected
    dynamic percentage of errors matching the sales_fact schema.
    """
    # 1. SETUP: Define a temporary file path
    test_filepath = tmp_path / "test_messy_sales.csv"
    n_base = 970

    # Initialize the configuration dataclass
    # Setting chunk_size small to ensure the while loop executes multiple times for coverage
    config = MessyDataConfig(n_base=n_base, chunk_size=500)

    # 2. EXECUTE: Run the generator targeting the temporary path with the config
    df_returned = generate_messy_data(filepath=str(test_filepath), config=config)

    # 3. ASSERT: File creation and Return Type
    assert test_filepath.exists(), "The CSV file was not created."
    assert df_returned is None, "Function should return None (streams to disk) in chunked mode."

    # 4. ASSERT: Data structure
    df = pd.read_csv(test_filepath)

    # --- Calculate exact expected totals based on chunk math ---
    expected_total_rows = 0
    total_gen = 0
    while total_gen < n_base:
        chunk = min(config.chunk_size, n_base - total_gen)
        expected_total_rows += chunk + int(chunk * config.frac_exact_duplicates)
        total_gen += chunk

    # Calculate minimum expected anomalies (calculated globally for safety)
    expected_min_missing_date = int(n_base * config.frac_missing_date)
    expected_min_missing_qty = int(n_base * config.frac_missing_qty)
    expected_min_neg_qty = int(n_base * config.frac_negative_qty)
    expected_min_bad_sku = int(n_base * config.frac_bad_sku_format)
    expected_min_missing_sku = int(n_base * config.frac_missing_sku)
    expected_min_missing_price = int(n_base * config.frac_missing_price)
    expected_min_unparseable_date = int(n_base * config.frac_unparseable_date)

    # Assert exact row count matches chunked generation math
    assert len(df) == expected_total_rows, f"Expected {expected_total_rows} rows, got {len(df)}"

    # Assert the new schema columns map perfectly to the sales_fact config
    expected_columns = ["transaction_id", "date", "sku_id", "warehouse_id", "quantity_sold", "unit_price"]
    assert list(df.columns) == expected_columns, f"Schema mismatch. Expected {expected_columns}, got {list(df.columns)}"

    # Check for missing dates
    missing_dates_count = df["date"].isna().sum()
    assert missing_dates_count >= expected_min_missing_date, f"Expected >= {expected_min_missing_date} missing dates, got {missing_dates_count}"

    # Check for unparseable dates
    unparseable_count = (df["date"] == "NOT_A_DATE").sum()
    assert unparseable_count >= expected_min_unparseable_date, f"Expected >= {expected_min_unparseable_date} unparseable dates, got {unparseable_count}"

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

    # Check for duplicated rows (Total duplicates = injected system duplicates + naturally occurring organic duplicates)
    duplicate_count = df.duplicated(keep="first").sum()
    # The minimum duplicates should be at least the difference between the total rows and base rows
    assert duplicate_count >= (expected_total_rows - n_base), f"Expected >= {(expected_total_rows - n_base)} exact duplicates, got {duplicate_count}"


def test_main_cli(tmp_path):
    """
    Simulates command line execution to ensure the main() block is covered
    by pytest, pushing coverage to 100%.
    """
    out_file = tmp_path / "cli_test_out.csv"

    # Mock the sys.argv list as if we typed this in the terminal
    test_args = [
        "make_messy_data.py",
        "--output", str(out_file),
        "--n-base", "100",
        "--chunk-size", "50"
    ]

    with patch("sys.argv", test_args):
        main()

    assert out_file.exists(), "CLI did not generate the output file."

    # Verify the CLI actually used our arguments
    df = pd.read_csv(out_file)
    # Total will be slightly higher than 100 due to injected duplicates
    assert len(df) >= 100, "CLI did not generate the expected number of base rows."