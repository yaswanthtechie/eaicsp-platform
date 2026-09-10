import pandas as pd


MIN_UNIQUE_VALUES = 10
LIKELY_THRESHOLD = 90.0
POSSIBLE_THRESHOLD = 50.0


def calculate_overlap(left_values, right_values):
    """
    Calculate value overlap using unique non-null values.

    overlap % = common values / size of the smaller set * 100
    """

    left_set = set(left_values.dropna().unique())
    right_set = set(right_values.dropna().unique())

    if not left_set or not right_set:
        return 0.0

    common_values = left_set & right_set

    return (
        len(common_values)
        / min(len(left_set), len(right_set))
    ) * 100


def _is_compatible_type(left_series, right_series):
    """
    Check whether two columns have compatible data types.

    String-like columns are compatible with string-like columns.
    Numeric columns are compatible with numeric columns.
    """

    left_is_numeric = isinstance(left_series.dtype, pd.CategoricalDtype)
    right_is_numeric = isinstance(right_series.dtype, pd.CategoricalDtype)

    left_is_string = (
        pd.api.types.is_object_dtype(left_series)
        or pd.api.types.is_string_dtype(left_series)
        or isinstance(left_series.dtype, pd.CategoricalDtype)
    )

    right_is_string = (
        pd.api.types.is_object_dtype(right_series)
        or pd.api.types.is_string_dtype(right_series)
        or isinstance(right_series.dtype, pd.CategoricalDtype)
    )

    if left_is_numeric and right_is_numeric:
        return True

    if left_is_string and right_is_string:
        return True

    return False


def _is_candidate_column(series):
    """
    A column is a candidate only when it has more than
    MIN_UNIQUE_VALUES unique non-null values.
    """

    unique_count = series.dropna().nunique()

    return unique_count > MIN_UNIQUE_VALUES


def discover_relationships(
    df_left: pd.DataFrame,
    df_right: pd.DataFrame,
):
    """
    Discover likely relationships between two datasets.

    Rules:
    - Compare only compatible data types.
    - Consider only columns with more than 10 unique values.
    - Calculate overlap using unique values.
    - >90%  -> likely join key
    - 50-90% -> possible relationship
    - <50% -> do not report

    Returns:
        List of relationship candidates.
    """

    if not isinstance(df_left, pd.DataFrame):
        raise TypeError("df_left must be a pandas DataFrame")

    if not isinstance(df_right, pd.DataFrame):
        raise TypeError("df_right must be a pandas DataFrame")

    relationships = []

    for left_column in df_left.columns:

        left_series = df_left[left_column]

        # Skip low-cardinality columns
        if not _is_candidate_column(left_series):
            continue

        for right_column in df_right.columns:

            right_series = df_right[right_column]

            # Skip low-cardinality columns
            if not _is_candidate_column(right_series):
                continue

            # Skip incompatible data types
            if not _is_compatible_type(
                left_series,
                right_series,
            ):
                continue

            overlap_percentage = calculate_overlap(
                left_series,
                right_series,
            )

            # Ignore noisy relationships below 50%
            if overlap_percentage < POSSIBLE_THRESHOLD:
                continue

            if overlap_percentage > LIKELY_THRESHOLD:
                classification = "likely_join_key"
            else:
                classification = "possible"

            relationships.append(
                {
                    "left_column": left_column,
                    "right_column": right_column,
                    "overlap_percentage": round(
                        overlap_percentage,
                        2,
                    ),
                    "classification": classification,
                }
            )

    # Highest overlap first
    relationships.sort(
        key=lambda relationship: relationship["overlap_percentage"],
        reverse=True,
    )

    return relationships