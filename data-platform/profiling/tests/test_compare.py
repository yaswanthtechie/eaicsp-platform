import pandas as pd

from src.compare import compare


# ---------------------------------
# Test 1 - No Drift
# ---------------------------------
def test_no_drift():

    old_df = pd.DataFrame({
        "sku_id": ["SKU001", "SKU002", "SKU003"],
        "warehouse_id": ["WH1", "WH2", "WH3"],
        "quantity_sold": [10, 20, 30]
    })

    # Exact copy = no changes
    new_df = old_df.copy()

    result = compare(old_df, new_df)

    assert result["status"] == "No Drift"


# ---------------------------------
# Test 2 - Minor Drift
# ---------------------------------
def test_minor_drift():

    old_df = pd.DataFrame({
        "warehouse_id": ["WH1", "WH2", "WH3"]
    })

    new_df = pd.DataFrame({
        "warehouse_id": ["WH1", "WH2", "WH4"]
    })

    result = compare(old_df, new_df)

    assert result["status"] == "Minor Drift"


# ---------------------------------
# Test 3 - Major Drift
# ---------------------------------
def test_major_drift():

    old_df = pd.DataFrame({
        "sku_id": ["SKU001", "SKU002", "SKU003"]
    })

    new_df = pd.DataFrame({
        "sku_id": ["SKU004", "SKU005", "SKU006"]
    })

    result = compare(old_df, new_df)

    assert result["status"] == "Major Drift"