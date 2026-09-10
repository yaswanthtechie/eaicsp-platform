import warnings

import pandas as pd
from sklearn.ensemble import RandomForestRegressor

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



def calculate_model_feature_importance(
    df: pd.DataFrame,
    target_col: str,
    n_estimators: int = 100
) -> pd.DataFrame:
    """
    Calculate model-based feature importance using a Random Forest.
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
    if n_estimators <= 0:
        raise ValueError(
            "n_estimators must be greater than 0."
        )
    numeric_data = data.select_dtypes(include="number")

    features = numeric_data.drop(columns=[target_col])

    if features.empty:
        raise ValueError("No numeric features available.")

    all_nan_columns = features.columns[features.isna().all()].tolist()

    if all_nan_columns:
        warnings.warn(
            f"Ignoring all-NaN features: {all_nan_columns}",
            UserWarning
        )
        features = features.drop(columns=all_nan_columns)

    valid_data = pd.concat(
        [features, data[target_col]],
        axis=1
    ).dropna()

    if valid_data.empty:
        raise ValueError("No valid rows available after removing NaN values.")

    X = valid_data.drop(columns=[target_col])
    y = valid_data[target_col]

    model = RandomForestRegressor(
        n_estimators=n_estimators,
        random_state=42
    )

    model.fit(X, y)

    importance = pd.Series(
        model.feature_importances_,
        index=X.columns,
        name="importance"
    )

    importance = importance.sort_values(ascending=False)

    return importance.to_frame()


def select_top_features(
    df: pd.DataFrame,
    target_col: str,
    n_features: int
) -> pd.DataFrame:
    """
    Select the top features using correlation and
    model-based feature importance.
    """

    if n_features <= 0:
        raise ValueError("n_features must be greater than 0.")

    correlations = calculate_feature_correlations(
        df,
        target_col
    )

    importance = calculate_model_feature_importance(
        df,
        target_col
    )

    scores = pd.DataFrame({
        "correlation": correlations["correlation"].abs(),
        "importance": importance["importance"]
    }).dropna()

    if scores.empty:
        raise ValueError("No valid features available for selection.")

    # Normalize both signals to 0-1.
    for column in ["correlation", "importance"]:
        minimum = scores[column].min()
        maximum = scores[column].max()

        if maximum == minimum:
            scores[f"{column}_normalized"] = 1.0
        else:
            scores[f"{column}_normalized"] = (
                (scores[column] - minimum)
                / (maximum - minimum)
            )

    scores["combined_score"] = (
        scores["correlation_normalized"]
        + scores["importance_normalized"]
    ) / 2

    scores = scores.sort_values(
        "combined_score",
        ascending=False
    )

    return scores.head(n_features)