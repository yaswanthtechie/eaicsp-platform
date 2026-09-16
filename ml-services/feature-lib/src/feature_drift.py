import pandas as pd
from scipy.stats import ks_2samp


def detect_feature_drift(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    features: list[str] | None = None,
    significance_level: float = 0.05,
    effect_size_threshold: float = 0.1,
) -> pd.DataFrame:
    """
    Detect distribution drift between reference and current feature data.

    Uses the two-sample Kolmogorov-Smirnov test for numeric features.

    A feature is considered drifted when both its p-value is below
    the configured significance level and its KS statistic is greater
    than or equal to the configured effect-size threshold.
    """

    if not 0 < significance_level < 1:
        raise ValueError(
            "significance_level must be between 0 and 1."
        )

    if not 0 < effect_size_threshold <= 1:
        raise ValueError(
            "effect_size_threshold must be between 0 and 1."
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
        current_numeric_columns = set(
            current_df.select_dtypes(include="number").columns
        )

        features = [
            column
            for column in reference_df.select_dtypes(include="number").columns
            if column in current_numeric_columns
        ]

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

        if current_values.empty:
            results.append(
                {
                    "feature": feature,
                    "statistic": float("nan"),
                    "p_value": float("nan"),
                    "is_drifted": True,
                    "reason": "no current values",
                }
            )
            continue

        if reference_values.empty:
            results.append(
                {
                    "feature": feature,
                    "statistic": float("nan"),
                    "p_value": float("nan"),
                    "is_drifted": False,
                    "reason": "no reference values",
                }
            )
            continue

        statistic, p_value = ks_2samp(
            reference_values,
            current_values,
            method="asymp",
        )

        is_drifted = (
            p_value < significance_level
            and statistic >= effect_size_threshold
        )

        results.append(
            {
                "feature": feature,
                "statistic": statistic,
                "p_value": p_value,
                "is_drifted": is_drifted,
                "reason": None,
            }
        )

    return pd.DataFrame(results)