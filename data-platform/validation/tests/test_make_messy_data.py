from pathlib import Path
from rules.custom_rules import standardize_dates
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


def test_key_space_grows_with_row_count():
    """__post_init__ must leave room for one unique composite key per base row."""
    cfg = MessyDataConfig(n_base=20000)
    n_dates = len(pd.date_range(cfg.start_date, cfg.end_date, freq=cfg.date_freq))
    n_keys = n_dates * (cfg.sku_end_range - cfg.sku_start_range) * len(cfg.warehouses)
    assert cfg.sku_end_range > 1050
    assert n_keys >= cfg.n_base


def test_default_config_is_unchanged_in_shape():
    """The default demo run keeps its configured dates, SKUs and warehouses."""
    cfg = MessyDataConfig()
    assert cfg.end_date == "2024-04-02"
    assert cfg.sku_end_range == 1050
    assert cfg.warehouses == ["WH-01", "WH-02", "WH-03", "WH-04"]


def test_sku_range_never_narrower_than_configured():
    cfg = MessyDataConfig(n_base=10, sku_end_range=1500)
    assert cfg.sku_end_range == 1500


def test_warehouses_extend_when_sku_ids_run_out():
    """5 dates x 8999 SKUs x 4 warehouses = 179,980 keys, fewer than 200,000 rows."""
    cfg = MessyDataConfig(n_base=200_000, end_date="2024-01-05")
    assert cfg.sku_end_range == 9999
    assert cfg.warehouses[-1] == "WH-05"
    assert cfg.end_date == "2024-01-05"  # date range untouched: date_in_range checks it
    n_keys = 5 * (cfg.sku_end_range - cfg.sku_start_range) * len(cfg.warehouses)
    assert n_keys >= cfg.n_base


def test_base_rows_get_unique_composite_keys(tmp_path):
    """With corruption and duplicate injection switched off, no two rows share a key."""
    out = tmp_path / "clean_keys.csv"
    cfg = MessyDataConfig(
        n_base=3000, chunk_size=700, frac_missing_qty=0, frac_negative_qty=0, frac_bad_sku_format=0,
        frac_missing_sku=0, frac_missing_warehouse_id=0, frac_missing_date=0, frac_exact_duplicates=0,
        frac_missing_price=0, frac_unparseable_date=0,
    )
    generate_messy_data(out, cfg)
    # Normalise the three date formats the same way the pipeline does
    df = standardize_dates(pd.read_csv(out), field="date")

    assert len(df) == 3000
    assert not df.duplicated(subset=["date", "sku_id", "warehouse_id"]).any()


def test_large_generated_batch_is_not_rejected(tmp_path):
    """
    The behaviour __post_init__ exists for: a 20k-row file must not be rejected
    just because random keys collided.
    """
    from src.validator import DataValidator

    out = tmp_path / "large.csv"
    generate_messy_data(out, MessyDataConfig(n_base=20_000))
    df = pd.read_csv(out)

    config = Path(__file__).resolve().parent.parent / "configs" / "sales_rules.yaml"
    report = DataValidator.from_config(str(config)).validate(df)

    assert report.batch_rejected is False, report.rejection_reasons