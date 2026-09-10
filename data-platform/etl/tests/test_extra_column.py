import pandas as pd

from data_contract import validate_schema


def test_extra_column():

    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01"]),
        "sku_id": ["SKU001"],
        "warehouse_id": ["WH001"],
        "quantity_sold": [10],
        "unit_price": [100],
        "extra_column": ["extra"]
    })

    assert validate_schema(df) is True