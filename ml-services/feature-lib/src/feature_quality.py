import pandas as pd


def score_feature_quality(
    df: pd.DataFrame,
    null_threshold: float = 0.20,
    instability_threshold: float = 10.0,
) -> pd.DataFrame:
    """
    Score feature quality based on null rate and instability.

    A feature is flagged as risky when its null rate reaches
    the configured threshold or when its coefficient of variation
    reaches the configured instability threshold.
    """

    results = []

    for column in df.columns:
        null_rate = df[column].isna().mean()

        risk = "safe"
        reason = None

        if null_rate >= null_threshold:
            risk = "risky"
            reason = f"High null rate: {null_rate:.1%}"

        elif pd.api.types.is_numeric_dtype(df[column]):
            mean = df[column].mean()
            std = df[column].std()

            if mean != 0 and pd.notna(mean) and pd.notna(std):
                coefficient_of_variation = abs(std / mean)

                if coefficient_of_variation >= instability_threshold:
                    risk = "risky"
                    reason = (
                        f"High variability: coefficient of variation "
                        f"{coefficient_of_variation:.2f}"
                    )

        results.append(
            {
                "feature": column,
                "null_rate": null_rate,
                "risk": risk,
                "reason": reason,
            }
        )

    return pd.DataFrame(results)