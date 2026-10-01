import pandas as pd

from src.external_regressors import (
    add_external_regressors,
    validate_external_regressors,
)


def test_external_regressors_are_added():
    df = pd.DataFrame({
        "date": pd.to_datetime([
            "2025-01-01",
            "2025-03-01",
            "2025-12-01",
        ]),
        "quantity_sold": [100, 120, 150],
    })

    result = add_external_regressors(df)

    assert "is_holiday" in result.columns
    assert "promotion" in result.columns
    assert "weather_index" in result.columns


def test_external_regressors_are_valid():
    df = pd.DataFrame({
        "is_holiday": [0, 1],
        "promotion": [0, 1],
        "weather_index": [0.2, 0.8],
    })

    validate_external_regressors(df)