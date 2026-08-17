import pandas as pd


def calculate_feature_correlations(
    df: pd.DataFrame,
    target_col: str
) -> pd.DataFrame:
    """
    Calculate correlations between numeric features and the target.
    """

    data = df.copy()

    if target_col not in data.columns:
        raise ValueError(
            f"Target column '{target_col}' not found in dataframe."
        )

    if not pd.api.types.is_numeric_dtype(data[target_col]):
        raise ValueError(
            f"Target column '{target_col}' must be numeric."
        )

    numeric_data = data.select_dtypes(include="number")

    correlations = numeric_data.corr()[target_col]

    correlations = correlations.drop(target_col)

    correlations = correlations.dropna()

    correlations = correlations.reindex(
        correlations.abs().sort_values(ascending=False).index
    )

    return correlations.rename("correlation").to_frame()
