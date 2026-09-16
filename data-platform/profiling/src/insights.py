import pandas as pd


def generate_insights(df, report):
    """
    Generate plain-English insights from profiling results.
    """
    insights = []

    # 1. Missing-value insight
    column_summary = report.get("column_summary", [])

    for column in column_summary:
        null_percent = column.get("null_percent", 0)

        if null_percent > 0:
            insights.append(
                f"{column['column']} has {null_percent}% missing values."
            )

    # 2. Outlier insight
    outliers = report.get("outliers", {})

    for column, details in outliers.items():
        outlier_count = details.get("outlier_count", 0)

        if outlier_count > 0:
            insights.append(
                f"{column} contains {outlier_count} detected outliers."
            )

    # 3. Dominant category insight
    for column in df.select_dtypes(include=["object", "category", "string"]).columns:
        series = df[column].dropna()

        if series.empty:
            continue

        value_counts = series.value_counts(normalize=True)

        top_value = value_counts.index[0]
        top_percentage = round(value_counts.iloc[0] * 100, 2)

        if top_percentage >= 40:
            insights.append(
                f"{top_value} accounts for {top_percentage}% "
                f"of all records in {column}."
            )

    # 4. Strong-correlation insight
    top_correlations = report.get("top_correlations", [])

    for correlation in top_correlations:
        value = correlation.get("correlation")

        if value is None:
            continue

        if abs(value) >= 0.8:
            direction = "positive" if value > 0 else "negative"

            insights.append(
                f"{correlation['column1']} and "
                f"{correlation['column2']} have a strong "
                f"{direction} correlation of {value}."
            )

    # 5. Quality-score insight
    quality_scorecard = report.get("quality_scorecard", {})
    overall_score = quality_scorecard.get("overall_score")

    if overall_score is not None:
        insights.append(
            f"Overall data quality score is {overall_score} out of 100."
        )

    return insights