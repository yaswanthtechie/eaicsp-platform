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


def test_structural_compatibility():

    old_df = pd.DataFrame({
        "sku_id": ["SKU001", "SKU002"],
        "warehouse_id": ["WH1", "WH2"],
        "quantity_sold": [10, 20]
    })

    new_df = pd.DataFrame({
        "sku_id": ["SKU003", "SKU004"],
        "warehouse_id": ["WH1", "WH2"],
        "quantity_sold": [30, 40]
    })

    result = compare(old_df, new_df)

    schema = result["schema_compatibility"]

    assert schema["shared_columns"] == [
        "quantity_sold",
        "sku_id",
        "warehouse_id"
    ]

    assert schema["only_in_old"] == []
    assert schema["only_in_new"] == []

    compatible_columns = [
        item["column"]
        for item in schema["compatible_types"]
    ]

    assert compatible_columns == [
        "quantity_sold",
        "sku_id",
        "warehouse_id"
    ]

    assert schema["incompatible_types"] == []

def test_structural_comparison_detects_new_column():

    old_df = pd.DataFrame({
        "sku_id": ["SKU001"],
        "quantity_sold": [10]
    })

    new_df = pd.DataFrame({
        "sku_id": ["SKU001"],
        "quantity_sold": [10],
        "unit_price": [100.0]
    })

    result = compare(old_df, new_df)

    schema = result["schema_compatibility"]

    assert schema["shared_columns"] == [
        "quantity_sold",
        "sku_id"
    ]

    assert schema["only_in_old"] == []
    assert schema["only_in_new"] == ["unit_price"]

def test_structural_comparison_detects_removed_column():

    old_df = pd.DataFrame({
        "sku_id": ["SKU001"],
        "quantity_sold": [10],
        "unit_price": [100.0]
    })

    new_df = pd.DataFrame({
        "sku_id": ["SKU001"],
        "quantity_sold": [10]
    })

    result = compare(old_df, new_df)

    schema = result["schema_compatibility"]

    assert schema["only_in_old"] == ["unit_price"]
    assert schema["only_in_new"] == []

def test_structural_comparison_detects_incompatible_types():

    old_df = pd.DataFrame({
        "sku_id": ["SKU001", "SKU002"],
        "quantity_sold": [10, 20]
    })

    new_df = pd.DataFrame({
        "sku_id": ["SKU001", "SKU002"],
        "quantity_sold": ["10", "20"]
    })

    result = compare(old_df, new_df)

    schema = result["schema_compatibility"]

    assert schema["incompatible_types"] == [{
        "column": "quantity_sold",
        "old_dtype": "int64",
        "new_dtype": "object"
    }]


# ---------------------------------
# Round 5 - Categorical Drift Tests
# ---------------------------------

def test_categorical_drift_detects_appeared_category():

    old_df = pd.DataFrame({
        "warehouse_id": [
            "WH1", "WH1", "WH2", "WH2"
        ]
    })

    new_df = pd.DataFrame({
        "warehouse_id": [
            "WH1", "WH1", "WH2", "WH3"
        ]
    })

    result = compare(old_df, new_df)

    categorical = result["categorical_drift"]

    assert "warehouse_id" in categorical
    assert categorical["warehouse_id"]["appeared"] == ["WH3"]


def test_categorical_drift_detects_disappeared_category():

    old_df = pd.DataFrame({
        "warehouse_id": [
            "WH1", "WH2", "WH2", "WH3"
        ]
    })

    new_df = pd.DataFrame({
        "warehouse_id": [
            "WH1", "WH2", "WH2", "WH1"
        ]
    })

    result = compare(old_df, new_df)

    categorical = result["categorical_drift"]

    assert "warehouse_id" in categorical
    assert categorical["warehouse_id"]["disappeared"] == ["WH3"]


def test_categorical_drift_detects_proportion_change():

    old_df = pd.DataFrame({
        "warehouse_id": [
            "WH1", "WH1", "WH1", "WH1",
            "WH2", "WH2", "WH2", "WH2"
        ]
    })

    new_df = pd.DataFrame({
        "warehouse_id": [
            "WH1", "WH1",
            "WH2", "WH2", "WH2", "WH2",
            "WH2", "WH2"
        ]
    })

    result = compare(old_df, new_df)

    categorical = result["categorical_drift"]

    changes = categorical["warehouse_id"]["proportion_changes"]

    changed_categories = [
        item["category"]
        for item in changes
    ]

    assert "WH1" in changed_categories
    assert "WH2" in changed_categories