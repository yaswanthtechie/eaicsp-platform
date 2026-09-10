import numbers
import warnings

import pandas as pd
from scipy.stats import pearsonr
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


def calculate_feature_significance(
    df: pd.DataFrame,
    target_col: str,
    significance_level: float = 0.05
) -> pd.DataFrame:
    """
    Calculate Pearson correlation, p-value, and statistical significance
    for each numeric feature against the target.

    Features with fewer than 3 valid observations are skipped because
    statistical significance cannot be reliably calculated.
    """

    if target_col not in df.columns:
        raise ValueError(
            f"Target column '{target_col}' not found."
        )

    if not pd.api.types.is_numeric_dtype(df[target_col]):
        raise ValueError(
            "Target column must be numeric."
        )

    if not 0 < significance_level < 1:
        raise ValueError(
            "significance_level must be between 0 and 1."
        )

    numeric_df = df.select_dtypes(include="number").copy()
    numeric_df = numeric_df.drop(
        columns=[target_col],
        errors="ignore"
    )

    results = []

    for feature in numeric_df.columns:
        pair = df[[feature, target_col]].dropna()

        if len(pair) < 3:
            continue

        correlation, p_value = pearsonr(
            pair[feature],
            pair[target_col]
        )

        results.append(
            {
                "feature": feature,
                "correlation": correlation,
                "p_value": p_value,
                "is_significant": p_value < significance_level,
            }
        )

    if not results:
        return pd.DataFrame(
            columns=[
                "feature",
                "correlation",
                "p_value",
                "is_significant",
            ]
        )

    return (
        pd.DataFrame(results)
        .sort_values("p_value", ascending=True)
        .reset_index(drop=True)
    )


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

    all_nan_columns = features.columns[
        features.isna().all()
    ].tolist()

    if all_nan_columns:
        warnings.warn(
            f"Ignoring all-NaN features: {all_nan_columns}",
            UserWarning
        )
        features = features.drop(columns=all_nan_columns)

    if features.empty:
        raise ValueError(
            "No valid features available after removing all-NaN features."
        )

    valid_data = pd.concat(
        [features, data[target_col]],
        axis=1
    ).dropna()

    if valid_data.empty:
        raise ValueError(
            "No valid rows available after removing NaN values."
        )

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
    df,
    target_col,
    n_features=5,
    significance_level=0.05,
):
    """
    Select the top features using correlation and model-based importance,
    with statistical significance as supporting evidence.

    Correlation and model importance are combined into the feature score.
    Statistical significance is reported and significant features are
    prioritized when ranking.
    """

    if not isinstance(n_features, numbers.Integral) or isinstance(
        n_features, bool
    ):
        raise ValueError(
            "n_features must be greater than 0."
        )

    if n_features <= 0:
        raise ValueError(
            "n_features must be greater than 0."
        )

    if not 0 < significance_level < 1:
        raise ValueError(
            "significance_level must be between 0 and 1."
        )

    correlations = (
        calculate_feature_correlations(
            df,
            target_col
        )
        .reset_index()
        .rename(columns={"index": "feature"})
    )

    importance = (
        calculate_model_feature_importance(
            df,
            target_col
        )
        .reset_index()
        .rename(columns={"index": "feature"})
    )

    significance = calculate_feature_significance(
        df,
        target_col,
        significance_level
    )

    scores = pd.DataFrame({
        "feature": correlations["feature"],
        "correlation": correlations["correlation"].abs()
    }).merge(
        importance[
            ["feature", "importance"]
        ],
        on="feature",
        how="inner"
    ).merge(
        significance[
            ["feature", "p_value", "is_significant"]
        ],
        on="feature",
        how="left"
    )

    if scores.empty:
        raise ValueError(
            "No valid features available for selection."
        )

    scores["is_significant"] = (
        scores["is_significant"]
        .fillna(False)
        .astype(bool)
    )

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
        ["is_significant", "combined_score"],
        ascending=[False, False]
    ).reset_index(drop=True)

    return scores.head(n_features).set_index("feature")