from pathlib import Path

import pandas as pd
from etl.src.quality_gate import quality_gate


def test_quality_gate():

    df = pd.DataFrame({
        "date": pd.to_datetime(["2026-07-20"] * 5),
        "sku_id": ["SKU101"] * 5,
        "warehouse_id": ["WH1"] * 5,
        "quantity_sold": [10, 10, 10, 10, 10],
        "unit_price": [100.0] * 5
    })

    batch = {
        "file_path": Path("sales_test_batch.csv"),
        "data": df,
    }

    result = quality_gate([batch])

    assert len(result) == 1
    assert len(result[0]["data"]) == 5