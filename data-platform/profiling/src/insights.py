# Concentration insight thresholds
CONCENTRATION_MAX_SHARE = 0.5
MIN_CATEGORIES_FOR_CONCENTRATION = 4
NEAR_UNIQUE_RATIO = 0.9


def generate_insights(df, report):
    """
    Generate plain-English insights from profiling results.
    """

    insights = []

    # ============================================================
    # 1. Missing-value insight
    # ============================================================

    column_summary = report.get("column_summary", [])

    for column in column_summary:
        null_percent = column.get("null_percent", 0)

        if null_percent > 0:
            insights.append(
                f"{column['column']} has {null_percent}% missing values."
            )

    # ============================================================
    # 2. Outlier insight
    # ============================================================

    outliers = report.get("outliers", {})

    for column, details in outliers.items():
        outlier_count = details.get("outlier_count", 0)

        if outlier_count > 0:
            insights.append(
                f"{column} contains {outlier_count} detected outliers."
            )

    # ============================================================
    # 3. Dominant category / concentration insight
    # ============================================================

    # Get columns classified as ID by the profiler.
    #
    # ID columns such as order_id, customer_id, sku_id, etc.
    # should not generate concentration insights.
    id_columns = {
        column["column"]
        for column in column_summary
        if column.get("role") == "ID"
    }

    for column in df.select_dtypes(
        include=["object", "category", "string"]
    ).columns:

        # --------------------------------------------------------
        # Skip columns already identified as IDs
        # --------------------------------------------------------

        if column in id_columns:
            continue

        series = df[column].dropna()

        if series.empty:
            continue

        value_counts = series.value_counts(normalize=True)

        # --------------------------------------------------------
        # Dominant single-category insight
        # --------------------------------------------------------

        top_value = value_counts.index[0]
        top_percentage = round(value_counts.iloc[0] * 100, 2)

        if top_percentage >= 40:
            insights.append(
                f"{top_value} accounts for {top_percentage}% "
                f"of all records in {column}."
            )

        # --------------------------------------------------------
        # Cumulative concentration insight
        # --------------------------------------------------------

        cumulative_percentage = value_counts.cumsum() * 100

        categories_needed = int(
            cumulative_percentage.ge(80).to_numpy().argmax() + 1
        )

        # --------------------------------------------------------
        # Concentration guard
        # --------------------------------------------------------
        #
        # We only want a concentration insight when a SMALL
        # minority of categories accounts for at least 80%
        # of the records.
        #
        # Example:
        #
        # 50 unique SKUs
        # 40 categories needed to reach 80%
        #
        # This is NOT meaningful concentration.
        #
        # Therefore we require:
        #
        # categories_needed <= 50% of all categories
        # --------------------------------------------------------

        concentration_limit = max(
            1,
            int(len(value_counts) * CONCENTRATION_MAX_SHARE)
        )

        # --------------------------------------------------------
        # Near-unique guard
        # --------------------------------------------------------
        #
        # If almost every row has a different value, the column
        # behaves like an ID even if the profiler did not classify
        # it explicitly as an ID.
        # --------------------------------------------------------

        is_near_unique = (
            len(value_counts) / len(series) > NEAR_UNIQUE_RATIO
        )

        # --------------------------------------------------------
        # Final concentration condition
        # --------------------------------------------------------

        if (
            not is_near_unique
            and len(value_counts) >= MIN_CATEGORIES_FOR_CONCENTRATION
            and categories_needed <= concentration_limit
        ):
            # Correct grammar:
            #
            # 1 category
            # 2 categories
            noun = (
                "category"
                if categories_needed == 1
                else "categories"
            )

            insights.append(
                f"{categories_needed} {noun} in {column} "
                f"account for at least 80% of all records."
            )

    # ============================================================
    # 4. Strong-correlation insight
    # ============================================================

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

    # ============================================================
    # Return all generated insights
    # ============================================================

    return insights
