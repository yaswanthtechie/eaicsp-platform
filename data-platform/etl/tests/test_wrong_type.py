import pandas as pd
import pytest

from data_contract import validate_schema


def test_wrong_type():

    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01"]),
        "sku_id": ["SKU001"],
        "warehouse_id": ["WH001"],
        "quantity_sold": ["abc"],   # Wrong type
        "unit_price": [100]
    })

    with pytest.raises(TypeError):
        validate_schema(df)