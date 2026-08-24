import pandas as pd
import pytest

from data_contract import validate_schema


def test_missing_column():

    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01"]),
        "sku_id": ["SKU001"],
        "warehouse_id": ["WH001"],
        "quantity_sold": [10]
        # unit_price intentionally missing
    })

    with pytest.raises(ValueError):
        validate_schema(df)