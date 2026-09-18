import pandas as pd

from src.profiler import Profiler


def test_empty_dataframe():
    df = pd.DataFrame()

    profiler = Profiler()
    report = profiler.profile(df)

    assert report is not None
    assert report["shape"] == [0, 0]
    assert report["columns"] == []


def test_all_null_column():
    df = pd.DataFrame({
        "quantity_sold": [None, None, None, None]
    })

    profiler = Profiler()
    report = profiler.profile(df)

    assert report["column_summary"][0]["null_count"] == 4
    assert report["column_summary"][0]["null_percent"] == 100.0


def test_wrong_dtype():
    df = pd.DataFrame({
        "quantity_sold": ["ten", "twenty", "thirty"]
    })

    profiler = Profiler()
    report = profiler.profile(df)

    assert report["column_summary"][0]["dtype"] in ("object", "str")

def test_profiler_discovers_relationships():
    left = pd.DataFrame({
        "sku_id": [f"SKU{i:03d}" for i in range(1, 12)]
    })

    right = pd.DataFrame({
        "product_code": [f"SKU{i:03d}" for i in range(1, 12)]
    })

    profiler = Profiler()

    result = profiler.discover_relationships(
        left,
        right
    )

    assert len(result) == 1
    assert result[0]["left_column"] == "sku_id"
    assert result[0]["right_column"] == "product_code"
    assert result[0]["overlap_percentage"] == 100.0
    assert result[0]["classification"] == "likely_join_key"