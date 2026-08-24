import pandas as pd

from src.outliers import find_outliers


def analyze_anomaly_correlation(
    df: pd.DataFrame,
    outlier_column: str = "quantity_sold"
) -> dict:
    """
    Analyze whether rows containing outliers in one column
    also contain other data-quality issues.
    """

    if outlier_column not in df.columns:
        return {
            "column": outlier_column,
            "outlier_rows": 0,
            "findings": []
        }

    # Anomaly correlation applies only to numeric columns
    if not pd.api.types.is_numeric_dtype(df[outlier_column]):
        return {
            "column": outlier_column,
            "outlier_rows": 0,
            "findings": []
        }

    outlier_result = find_outliers(df[outlier_column])
    outlier_mask = outlier_result["outlier_mask"]

    outlier_rows = df.loc[outlier_mask]
    normal_rows = df.loc[~outlier_mask]

    findings = []

    if len(outlier_rows) == 0:
        return {
            "column": outlier_column,
            "outlier_rows": 0,
            "findings": []
        }

    # Check missing values in other columns
    for column in df.columns:
        if column == outlier_column:
            continue

        outlier_missing_rate = (
            outlier_rows[column].isna().mean() * 100
        )

        normal_missing_rate = (
            normal_rows[column].isna().mean() * 100
        )

        if outlier_missing_rate > 0:
            if normal_missing_rate > 0:
                likelihood = (
                    outlier_missing_rate / normal_missing_rate
                )
            else:
                likelihood = None

            findings.append({
                "column": column,
                "issue": "Missing values",
                "outlier_row_rate": round(outlier_missing_rate, 2),
                "normal_row_rate": round(normal_missing_rate, 2),
                "likelihood": (
                    round(likelihood, 2)
                    if likelihood is not None
                    else None
                )
            })

    # Check other numeric columns for outliers
    for column in df.columns:
        if column == outlier_column:
            continue

        if not pd.api.types.is_numeric_dtype(df[column]):
            continue

        other_outlier_result = find_outliers(df[column])
        other_outlier_mask = other_outlier_result["outlier_mask"]

        correlated_outliers = outlier_mask & other_outlier_mask

        correlated_count = int(correlated_outliers.sum())

        if correlated_count > 0:
            outlier_row_rate = (
                correlated_count / len(outlier_rows) * 100
            )

            findings.append({
                "column": column,
                "issue": "Other outliers",
                "outlier_row_count": correlated_count,
                "outlier_row_rate": round(outlier_row_rate, 2)
            })

    return {
        "column": outlier_column,
        "outlier_rows": int(len(outlier_rows)),
        "findings": findings
    }