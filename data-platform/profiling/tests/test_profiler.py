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

    assert pd.api.types.is_string_dtype(df["quantity_sold"])