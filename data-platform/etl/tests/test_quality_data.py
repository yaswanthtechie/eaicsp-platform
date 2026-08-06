import pandas as pd
from etl.src.quality_gate import quality_gate


def test_quality_gate():

    df = pd.DataFrame({
        "date": ["2026-07-20"],
        "sku_id": [101],
        "warehouse_id": [1],
        "quantity_sold": [10],
        "unit_price": [100]
    })

    result = quality_gate([df])

    assert len(result) == 1