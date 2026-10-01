
"""Point-in-time-correct feature joins."""

import pandas as pd


def asof_join(
    observations: pd.DataFrame,
    features: pd.DataFrame,
    observation_time: str,
    feature_time: str,
    by: str | list[str] | None = None,
    suffixes: tuple[str, str] = ("_observation", "_feature"),
) -> pd.DataFrame:
    """Attach the latest feature record available strictly before each observation.

    Original observation order and index are preserved. Exact timestamp matches
    are excluded to prevent point-in-time leakage.
    """
    if not isinstance(observations, pd.DataFrame):
        raise TypeError("observations must be a pandas DataFrame.")
    if not isinstance(features, pd.DataFrame):
        raise TypeError("features must be a pandas DataFrame.")
    if not isinstance(observation_time, str) or not isinstance(feature_time, str):
        raise TypeError("Time column names must be strings.")

    if observation_time not in observations.columns:
        raise ValueError(f"Missing observation time column: {observation_time}")
    if feature_time not in features.columns:
        raise ValueError(f"Missing feature time column: {feature_time}")

    by_cols = [by] if isinstance(by, str) else list(by or [])

    for column in by_cols:
        if column not in observations.columns:
            raise ValueError(
                f"Missing grouping column in observations: {column}"
            )
        if column not in features.columns:
            raise ValueError(
                f"Missing grouping column in features: {column}"
            )

    for column in by_cols:
        if observations[column].isna().any():
            raise ValueError(
                f"Observation grouping column cannot contain null values: {column}"
            )
        if features[column].isna().any():
            raise ValueError(
                f"Feature grouping column cannot contain null values: {column}"
            )

    if observations[observation_time].isna().any():
        raise ValueError("Observation timestamps cannot contain null values.")
    if features[feature_time].isna().any():
        raise ValueError("Feature timestamps cannot contain null values.")

    if observations.empty:
        return observations.copy()

    # Validate timestamp types when features are present. For empty features,
    # there are no timestamps to compare, so use the observation dtype.
    if not features.empty:
        if (
            observations[observation_time].dtype
            != features[feature_time].dtype
        ):
            raise TypeError(
                "Observation and feature time columns must have matching dtypes."
            )

    # No feature records: return observations and add missing feature columns.
    if features.empty:
        result = observations.copy()
        overlapping = (
            set(observations.columns) & set(features.columns)
        ) - set(by_cols)

        for column in features.columns:
            if column == feature_time or column in by_cols:
                continue

            output_column = (
                f"{column}{suffixes[1]}"
                if column in overlapping
                else column
            )

            if output_column not in result.columns:
                result[output_column] = pd.NA

        return result

    # Duplicate records at the same availability time within a group are
    # ambiguous, so reject them instead of selecting an arbitrary record.
    duplicate_keys = [*by_cols, feature_time]
    if features.duplicated(subset=duplicate_keys, keep=False).any():
        raise ValueError(
            "Feature records contain duplicate timestamps for the same "
            "grouping key."
        )

    order_col = "__asof_original_order__"
    while order_col in observations.columns or order_col in features.columns:
        order_col += "_"

    left = observations.copy()
    right = features.copy()
    left[order_col] = range(len(left))

    left = left.sort_values(observation_time, kind="mergesort")
    right = right.sort_values(feature_time, kind="mergesort")

    result = pd.merge_asof(
        left,
        right,
        left_on=observation_time,
        right_on=feature_time,
        by=by_cols or None,
        direction="backward",
        allow_exact_matches=False,
        suffixes=suffixes,
    )

    result = result.sort_values(order_col, kind="mergesort")
    result = result.drop(columns=[order_col])
    result.index = observations.index

    return result