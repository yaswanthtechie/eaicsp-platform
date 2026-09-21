import time

import pandas as pd

from src.profiler import Profiler


def test_profile_100k_rows():
    rows = 100_000

    df = pd.DataFrame({
        "quantity_sold": range(1, rows + 1),
        "unit_price": [100.0] * rows,
        "warehouse_id": ["WH1"] * rows,
        "sku_id": ["SKU001"] * rows
    })

    profiler = Profiler()

    start = time.perf_counter()

    report = profiler.profile(df)

    elapsed = time.perf_counter() - start

    print(f"\n100,000-row profiling time: {elapsed:.4f} seconds")

    assert report is not None
    assert elapsed < 30