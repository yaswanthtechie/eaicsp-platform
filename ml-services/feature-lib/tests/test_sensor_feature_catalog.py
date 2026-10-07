import pandas as pd

from feature_lib.feature_catalog import (
    generate_sensor_feature_catalog,
)


def test_sensor_catalog_documents_generated_features():
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=5),
        "temperature": [10, 12, 14, 16, 18],
        "humidity": [50, 52, 54, 56, 58],
    })

    catalog = generate_sensor_feature_catalog(
        df=df,
        sensor_cols=["temperature", "humidity"],
        timestamp_col="timestamp",
        window=2,
    )

    assert not catalog.empty
    assert list(catalog.columns) == [
        "feature", "type", "meaning", "version"
    ]
    assert set(catalog["version"]) == {"sensor-v1"}

    expected_types = {
        "Sensor Rolling Z-Score",
        "Sensor Rate of Change",
        "Sensor Rolling Min",
        "Sensor Rolling Max",
        "Cross-Sensor Ratio",
    }
    assert expected_types.issubset(set(catalog["type"]))

    assert catalog["meaning"].str.len().gt(0).all()


def test_sensor_catalog_documents_leakage_safe_rolling_features():
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=4),
        "temperature": [10, 20, 30, 40],
    })

    catalog = generate_sensor_feature_catalog(
        df=df,
        sensor_cols=["temperature"],
        timestamp_col="timestamp",
        window=2,
    )

    rolling = catalog[
        catalog["type"].isin([
            "Sensor Rolling Z-Score",
            "Sensor Rolling Min",
            "Sensor Rolling Max",
        ])
    ]

    assert not rolling.empty
    assert rolling["meaning"].str.contains(
        "previous", case=False
    ).all()