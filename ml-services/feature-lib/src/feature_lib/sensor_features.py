import pandas as pd
from numbers import Integral

from .asof_join import asof_join


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

    Historical rolling statistics and previous readings are attached
    using a strict point-in-time as-of join. Readings at the same
    timestamp as the observation are therefore excluded from history.
    Cross-sensor ratios use the current observation.

    The rolling ``window`` is based on the number of historical
    observations, not elapsed time. For example, ``window=7`` means
    the previous 7 historical sensor records, not the previous
    7 days or 7 hours. For irregularly sampled sensor data, those
    7 observations may span different amounts of elapsed time.
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
            raise ValueError(
                "Group columns must be distinct from timestamp and sensors."
            )

    if df[timestamp_col].isna().any():
        raise ValueError("Timestamp column must not contain null values.")

    if group_cols and df[group_cols].isna().any().any():
        raise ValueError("Group columns must not contain null values.")

    if not all(
        pd.api.types.is_numeric_dtype(df[col])
        for col in sensor_cols
    ):
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
            raise ValueError(
                "A sensor pair must contain two different sensors."
            )

    data = df.copy()
    data[timestamp_col] = pd.to_datetime(
        data[timestamp_col],
        errors="raise",
    )

    # Empty batch (e.g. a sensor with no new readings): return the
    # expected columns instead of failing inside the join.
    if data.empty:
        for col in sensor_cols:
            for name in (
                f"{col}_rolling_zscore_{window}",
                f"{col}_rate_of_change",
                f"{col}_rolling_min_{window}",
                f"{col}_rolling_max_{window}",
            ):
                data[name] = pd.Series(dtype="float64")
        for numerator, denominator in sensor_pairs:
            data[f"{numerator}_to_{denominator}_ratio"] = pd.Series(
                dtype="float64"
            )
        return data

    # ------------------------------------------------------------------
    # Build historical sensor records.
    #
    # Duplicate readings at the same timestamp are aggregated so that
    # one same-time reading cannot become another same-time reading's
    # "previous" observation.
    # ------------------------------------------------------------------
    history_keys = [timestamp_col]
    if group_cols:
        history_keys = [*group_cols, timestamp_col]

    history = (
        data[history_keys + sensor_cols]
        .groupby(
            history_keys,
            sort=True,
            dropna=False,
            as_index=False,
        )[sensor_cols]
        .mean()
    )

    # Stable chronological ordering.
    history = history.sort_values(
        history_keys,
        kind="mergesort",
    )

    history_feature_cols = []

    # ------------------------------------------------------------------
    # Calculate historical statistics INCLUDING each history record.
    #
    # The strict asof_join below will only select a history record
    # whose timestamp is strictly before the current observation.
    #
    # Therefore, for observation at time T:
    #   latest history record < T
    #   rolling statistics on that history record include its own value
    #   but never include the observation at T.
    #
    # The rolling window is based on the number of historical
    # observations, not elapsed time.
    # ------------------------------------------------------------------
    history_groupby = (
        history.groupby(
            group_cols,
            sort=False,
            dropna=False,
        )
        if group_cols
        else None
    )

    for col in sensor_cols:
        previous_name = f"__history_{col}_previous__"
        mean_name = f"__history_{col}_rolling_mean__"
        std_name = f"__history_{col}_rolling_std__"
        min_name = f"__history_{col}_rolling_min__"
        max_name = f"__history_{col}_rolling_max__"

        if history_groupby is not None:
            history[previous_name] = history_groupby[col].shift(0)

            history[mean_name] = history_groupby[col].transform(
                lambda s: s.rolling(
                    window,
                    min_periods=window,
                ).mean()
            )

            history[std_name] = history_groupby[col].transform(
                lambda s: s.rolling(
                    window,
                    min_periods=window,
                ).std(ddof=0)
            )

            history[min_name] = history_groupby[col].transform(
                lambda s: s.rolling(
                    window,
                    min_periods=window,
                ).min()
            )

            history[max_name] = history_groupby[col].transform(
                lambda s: s.rolling(
                    window,
                    min_periods=window,
                ).max()
            )

        else:
            history[previous_name] = history[col]

            history[mean_name] = history[col].rolling(
                window,
                min_periods=window,
            ).mean()

            history[std_name] = history[col].rolling(
                window,
                min_periods=window,
            ).std(ddof=0)

            history[min_name] = history[col].rolling(
                window,
                min_periods=window,
            ).min()

            history[max_name] = history[col].rolling(
                window,
                min_periods=window,
            ).max()

        history_feature_cols.extend(
            [
                previous_name,
                mean_name,
                std_name,
                min_name,
                max_name,
            ]
        )

    # Only the timestamp/group columns + historical features are needed
    # for the as-of join.
    history_features = history[
        history_keys + history_feature_cols
    ].copy()

    # ------------------------------------------------------------------
    # Strict point-in-time join.
    #
    # asof_join uses:
    #     feature_time < observation_time
    #
    # so an observation never sees a sensor record at its own timestamp.
    # ------------------------------------------------------------------
    joined = asof_join(
        data,
        history_features,
        observation_time=timestamp_col,
        feature_time=timestamp_col,
        by=group_cols,
    )

    for col in sensor_cols:
        previous = joined[f"__history_{col}_previous__"]
        history_mean = joined[f"__history_{col}_rolling_mean__"]
        history_std = joined[f"__history_{col}_rolling_std__"]
        history_min = joined[f"__history_{col}_rolling_min__"]
        history_max = joined[f"__history_{col}_rolling_max__"]

        joined[f"{col}_rolling_zscore_{window}"] = (
            (joined[col] - history_mean)
            / history_std.where(history_std != 0)
        )

        joined[f"{col}_rate_of_change"] = (
            (joined[col] - previous)
            / previous.abs().where(previous != 0)
        )

        joined[f"{col}_rolling_min_{window}"] = history_min
        joined[f"{col}_rolling_max_{window}"] = history_max

    # Cross-sensor ratios intentionally use the current observation.
    for numerator, denominator in sensor_pairs:
        joined[f"{numerator}_to_{denominator}_ratio"] = (
            joined[numerator]
            / joined[denominator].where(joined[denominator] != 0)
        )

    # Remove implementation-only columns.
    joined = joined.drop(
        columns=history_feature_cols,
        errors="ignore",
    )

    return joined