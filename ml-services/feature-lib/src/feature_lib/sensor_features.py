
import pandas as pd
from numbers import Integral


def add_sensor_features(
    df: pd.DataFrame,
    sensor_cols: list[str],
    timestamp_col: str,
    window: int = 7,
    group_cols: list[str] | None = None,
    sensor_pairs: list[tuple[str, str]] | None = None,
) -> pd.DataFrame:
    """
    Add leakage-safe time-series features for sensor readings.

    Rolling statistics use only earlier readings.
    Rate of change compares the current reading with the
    previous reading. Cross-sensor ratios use readings
    from the same observation.
    """
    if not isinstance(df, pd.DataFrame):
        raise ValueError("df must be a pandas DataFrame.")

    if not isinstance(window, Integral) or isinstance(window, bool) or window <= 0:
        raise ValueError("window must be a positive integer.")

    if not isinstance(timestamp_col, str) or timestamp_col not in df.columns:
        raise ValueError("timestamp_col must name an existing column.")

    if not sensor_cols or not all(
        isinstance(col, str) and col in df.columns for col in sensor_cols
    ):
        raise ValueError("sensor_cols must contain existing column names.")

    if len(set(sensor_cols)) != len(sensor_cols):
        raise ValueError("sensor_cols must not contain duplicates.")

    if group_cols is not None:
        if not all(col in df.columns for col in group_cols):
            raise ValueError("All group columns must exist in the dataframe.")
        if timestamp_col in group_cols or any(
            col in sensor_cols for col in group_cols
        ):
            raise ValueError("Group columns must be distinct from timestamp and sensors.")

    if df[timestamp_col].isna().any():
        raise ValueError("Timestamp column must not contain null values.")

    if group_cols and df[group_cols].isna().any().any():
        raise ValueError("Group columns must not contain null values.")

    if not all(pd.api.types.is_numeric_dtype(df[col]) for col in sensor_cols):
        raise ValueError("All sensor columns must be numeric.")

    if sensor_pairs is None:
        sensor_pairs = [
            (sensor_cols[i], sensor_cols[j])
            for i in range(len(sensor_cols))
            for j in range(i + 1, len(sensor_cols))
        ]

    for numerator, denominator in sensor_pairs:
        if numerator not in sensor_cols or denominator not in sensor_cols:
            raise ValueError("sensor_pairs must reference sensor_cols.")
        if numerator == denominator:
            raise ValueError("A sensor pair must contain two different sensors.")

    data = df.copy()
    data[timestamp_col] = pd.to_datetime(data[timestamp_col], errors="raise")

    # Stable chronological ordering, while retaining original row order.
    data["__sensor_original_order__"] = range(len(data))
    data = data.sort_values(
        [*group_cols, timestamp_col] if group_cols else [timestamp_col],
        kind="mergesort",
    )

    groupby = (
        data.groupby(group_cols, sort=False, dropna=False)
        if group_cols else None
    )

    for col in sensor_cols:
        previous = (
            groupby[col].shift(1) if groupby is not None
            else data[col].shift(1)
        )

        history = (
            groupby[col].transform(
                lambda s: s.shift(1).rolling(window, min_periods=window).mean()
            ) if groupby is not None
            else data[col].shift(1).rolling(window, min_periods=window).mean()
        )
        history_std = (
            groupby[col].transform(
                lambda s: s.shift(1).rolling(
                    window, min_periods=window
                ).std(ddof=0)
            ) if groupby is not None
            else data[col].shift(1).rolling(
                window, min_periods=window
            ).std(ddof=0)
        )
        history_min = (
            groupby[col].transform(
                lambda s: s.shift(1).rolling(window, min_periods=window).min()
            ) if groupby is not None
            else data[col].shift(1).rolling(window, min_periods=window).min()
        )
        history_max = (
            groupby[col].transform(
                lambda s: s.shift(1).rolling(window, min_periods=window).max()
            ) if groupby is not None
            else data[col].shift(1).rolling(window, min_periods=window).max()
        )

        data[f"{col}_rolling_zscore_{window}"] = (
            (data[col] - history) / history_std.where(history_std != 0)
        )
        data[f"{col}_rate_of_change"] = (
            (data[col] - previous) / previous.abs().where(previous != 0)
        )
        data[f"{col}_rolling_min_{window}"] = history_min
        data[f"{col}_rolling_max_{window}"] = history_max

    for numerator, denominator in sensor_pairs:
        data[f"{numerator}_to_{denominator}_ratio"] = (
            data[numerator] / data[denominator].where(data[denominator] != 0)
        )

    data = data.sort_values("__sensor_original_order__", kind="mergesort")
    data = data.drop(columns="__sensor_original_order__")
    return data