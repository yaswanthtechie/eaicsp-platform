import numpy as np
import pandas as pd
import pytest

from feature_lib.sensor_features import add_sensor_features


def test_sensor_features_create_expected_columns():
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=5),
        "temperature": [10, 12, 14, 16, 18],
        "humidity": [50, 52, 54, 56, 58],
    })

    result = add_sensor_features(
        df,
        sensor_cols=["temperature", "humidity"],
        timestamp_col="timestamp",
        window=2,
    )

    expected = [
        "temperature_rolling_min_2",
        "temperature_rolling_max_2",
        "temperature_rolling_zscore_2",
        "temperature_rate_of_change",
        "humidity_rolling_min_2",
        "humidity_rolling_max_2",
        "humidity_rolling_zscore_2",
        "humidity_rate_of_change",
        "temperature_to_humidity_ratio",
    ]

    for column in expected:
        assert column in result.columns


def test_rolling_features_do_not_use_current_or_future_values():
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=4),
        "temperature": [10, 20, 30, 40],
    })

    result = add_sensor_features(
        df,
        sensor_cols=["temperature"],
        timestamp_col="timestamp",
        window=2,
    )

    # At row 2, rolling min/max use only prior rows 0 and 1.
    assert result.loc[2, "temperature_rolling_min_2"] == 10
    assert result.loc[2, "temperature_rolling_max_2"] == 20

    # Changing current and future values must not change
    # the historical rolling baseline at row 2.
    changed = df.copy()
    changed.loc[2, "temperature"] = 300
    changed.loc[3, "temperature"] = 400

    changed_result = add_sensor_features(
        changed,
        sensor_cols=["temperature"],
        timestamp_col="timestamp",
        window=2,
    )

    assert (
        result.loc[2, "temperature_rolling_min_2"]
        == changed_result.loc[2, "temperature_rolling_min_2"]
    )
    assert (
        result.loc[2, "temperature_rolling_max_2"]
        == changed_result.loc[2, "temperature_rolling_max_2"]
    )


def test_sensor_features_do_not_mix_groups():
    df = pd.DataFrame({
        "timestamp": pd.to_datetime([
            "2026-01-01", "2026-01-02",
            "2026-01-01", "2026-01-02",
        ]),
        "sensor_id": ["A", "A", "B", "B"],
        "temperature": [10, 20, 100, 200],
    })

    result = add_sensor_features(
        df,
        sensor_cols=["temperature"],
        timestamp_col="timestamp",
        window=1,
        group_cols=["sensor_id"],
    )
    # Each sensor's rolling baseline uses only its own prior reading.
    assert result.loc[1, "temperature_rolling_min_1"] == 10
    assert result.loc[1, "temperature_rolling_max_1"] == 10
    assert result.loc[3, "temperature_rolling_min_1"] == 100
    assert result.loc[3, "temperature_rolling_max_1"] == 100


def test_sensor_features_restore_original_row_order():
    df = pd.DataFrame({
        "timestamp": pd.to_datetime([
            "2026-01-03", "2026-01-01", "2026-01-02"
        ]),
        "temperature": [30, 10, 20],
    })

    result = add_sensor_features(
        df,
        sensor_cols=["temperature"],
        timestamp_col="timestamp",
        window=1,
    )

    assert result["timestamp"].tolist() == df["timestamp"].tolist()


def test_zero_previous_value_gives_nan_rate_of_change():
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=2),
        "temperature": [0, 10],
    })

    result = add_sensor_features(
        df,
        sensor_cols=["temperature"],
        timestamp_col="timestamp",
        window=1,
    )

    assert np.isnan(result.loc[1, "temperature_rate_of_change"])


def test_invalid_window_is_rejected():
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=2),
        "temperature": [10, 20],
    })

    with pytest.raises((TypeError, ValueError)):
        add_sensor_features(
            df,
            sensor_cols=["temperature"],
            timestamp_col="timestamp",
            window=0,
        )