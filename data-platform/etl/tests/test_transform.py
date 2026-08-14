import pandas as pd
from etl.src.transform import transform_data


def test_transform_data():

    df = pd.DataFrame({
        "date": ["2026-07-20"],
        "sku_id": [101],
        "warehouse_id": [1],
        "quantity_sold": [10],
        "unit_price": [100]
    })

    result = transform_data([df])

    assert len(result) == 1