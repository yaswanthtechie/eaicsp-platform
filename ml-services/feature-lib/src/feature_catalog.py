import pandas as pd


def generate_feature_catalog(
    df: pd.DataFrame,
    date_col: str,
    target_col: str,
    config: dict | None = None,
    feature_version: str = "v1",
    group_cols=None,
) -> pd.DataFrame:
    """
    Generate a human-readable catalog of generated features.
    """

    from src.build_features import build_all_features

    features = build_all_features(
        df=df,
        date_col=date_col,
        target_col=target_col,
        config=config,
        feature_version=feature_version,
        group_cols=group_cols,
    )

    catalog = []

    for column in features.columns:
        if column in df.columns:
            continue

        if "_lag_" in column:
            meaning = "Previous observation value at the configured lag."
            feature_type = "Lag"

        elif "_roll_mean_" in column:
            meaning = "Rolling mean of previous observations."
            feature_type = "Rolling Mean"

        elif "_roll_std_" in column:
            meaning = "Rolling standard deviation of previous observations."
            feature_type = "Rolling Std"

        elif column == "day_of_week":
            meaning = "Day of the week represented as a numeric value."
            feature_type = "Calendar"

        elif column == "month":
            meaning = "Month extracted from the date."
            feature_type = "Calendar"

        elif column == "day_of_month":
            meaning = "Day of the month extracted from the date."
            feature_type = "Calendar"

        elif column == "is_weekend":
            meaning = "Indicates whether the date falls on a weekend."
            feature_type = "Calendar"

        elif column == "is_month_start":
            meaning = "Indicates whether the date is the first day of a month."
            feature_type = "Calendar"

        elif column == "is_month_end":
            meaning = "Indicates whether the date is the last day of a month."
            feature_type = "Calendar"

        elif column == "is_holiday":
            meaning = "Indicates whether the date is an Indian public holiday."
            feature_type = "Holiday"

        elif "_x_" in column:
            meaning = "Interaction between the component features."
            feature_type = "Interaction"

        else:
            meaning = "Generated feature."
            feature_type = "Other"

        catalog.append(
            {
                "feature": column,
                "type": feature_type,
                "meaning": meaning,
                "version": feature_version,
            }
        )

    return pd.DataFrame(catalog)