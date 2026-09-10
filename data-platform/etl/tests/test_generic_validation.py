import pandas as pd
import pytest

from etl.src.data_contract import validate_schema_against
from etl.src.config_loader import load_pipeline_config


CONFIG = load_pipeline_config()
SALES_SCHEMA = CONFIG.get_source("sales").columns
INVENTORY_SCHEMA = CONFIG.get_source("inventory").columns


def test_valid_sales_batch_passes():
    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01"]),
        "sku_id": ["SKU1"],
        "warehouse_id": ["WH1"],
        "quantity_sold": [10],
        "unit_price": [19.99],
    })
    assert validate_schema_against(df, SALES_SCHEMA) is True


def test_valid_inventory_batch_passes():
    df = pd.DataFrame({
        "snapshot_date": pd.to_datetime(["2024-01-01"]),
        "sku_id": ["SKU1"],
        "warehouse_id": ["WH1"],
        "quantity_on_hand": [100],
    })
    assert validate_schema_against(df, INVENTORY_SCHEMA) is True


def test_missing_required_column_raises():
    df = pd.DataFrame({
        "snapshot_date": pd.to_datetime(["2024-01-01"]),
        "sku_id": ["SKU1"],
        # warehouse_id missing
        "quantity_on_hand": [100],
    })
    with pytest.raises(ValueError):
        validate_schema_against(df, INVENTORY_SCHEMA)


def test_wrong_type_raises():
    df = pd.DataFrame({
        "snapshot_date": pd.to_datetime(["2024-01-01"]),
        "sku_id": ["SKU1"],
        "warehouse_id": ["WH1"],
        "quantity_on_hand": ["not_a_number"],
    })
    with pytest.raises(TypeError):
        validate_schema_against(df, INVENTORY_SCHEMA)


def test_empty_dataframe_with_correct_columns_passes():
    df = pd.DataFrame({
        "snapshot_date": pd.Series([], dtype="datetime64[ns]"),
        "sku_id": pd.Series([], dtype="object"),
        "warehouse_id": pd.Series([], dtype="object"),
        "quantity_on_hand": pd.Series([], dtype="int64"),
    })
    assert validate_schema_against(df, INVENTORY_SCHEMA) is True
