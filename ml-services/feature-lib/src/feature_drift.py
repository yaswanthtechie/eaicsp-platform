import pandas as pd
from scipy.stats import ks_2samp


def detect_feature_drift(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    features: list[str] | None = None,
    significance_level: float = 0.05,
) -> pd.DataFrame:
    """
    Detect distribution drift between reference and current feature data.

    Uses the two-sample Kolmogorov-Smirnov test for numeric features.

    A feature is considered drifted when its p-value is below
    the configured significance level.
    """

    if not 0 < significance_level < 1:
        raise ValueError(
            "significance_level must be between 0 and 1."
        )

    if not isinstance(reference_df, pd.DataFrame):
        raise ValueError(
            "reference_df must be a pandas DataFrame."
        )

    if not isinstance(current_df, pd.DataFrame):
        raise ValueError(
            "current_df must be a pandas DataFrame."
        )

    if features is None:
        features = list(
            set(reference_df.select_dtypes(include="number").columns)
            & set(current_df.select_dtypes(include="number").columns)
        )

    if not features:
        raise ValueError(
            "No common numeric features available for drift detection."
        )

    results = []

    for feature in features:
        if feature not in reference_df.columns:
            raise ValueError(
                f"Feature '{feature}' not found in reference data."
            )

        if feature not in current_df.columns:
            raise ValueError(
                f"Feature '{feature}' not found in current data."
            )

        if not pd.api.types.is_numeric_dtype(
            reference_df[feature]
        ):
            raise ValueError(
                f"Feature '{feature}' must be numeric."
            )

        if not pd.api.types.is_numeric_dtype(
            current_df[feature]
        ):
            raise ValueError(
                f"Feature '{feature}' must be numeric."
            )

        reference_values = reference_df[feature].dropna()
        current_values = current_df[feature].dropna()

        if reference_values.empty or current_values.empty:
            results.append(
                {
                    "feature": feature,
                    "statistic": float("nan"),
                    "p_value": float("nan"),
                    "is_drifted": False,
                }
            )
            continue

        statistic, p_value = ks_2samp(
            reference_values,
            current_values,
            method="asymp",
        )

        results.append(
            {
                "feature": feature,
                "statistic": statistic,
                "p_value": p_value,
                "is_drifted": p_value < significance_level,
            }
        )

    return pd.DataFrame(results)