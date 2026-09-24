import re
from .build_features import build_all_features
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
            lag_match = re.search(r"_lag_(\d+)$", column)
            lag = lag_match.group(1) if lag_match else "configured"

            meaning = (
                f"Target value from {lag} observation(s) earlier; "
                "shifted backward to avoid using the current target "
                "and prevent data leakage."
            )
            feature_type = "Lag"

        elif "_roll_mean_" in column:
            window_match = re.search(r"_roll_mean_(\d+)$", column)
            window = (
                window_match.group(1)
                if window_match
                else "configured"
            )

            meaning = (
                f"Mean of the previous {window} observations; "
                "the rolling calculation is shifted by one observation "
                "to avoid using the current target and prevent data leakage."
            )
            feature_type = "Rolling Mean"

        elif "_roll_std_" in column:
            window_match = re.search(r"_roll_std_(\d+)$", column)
            window = (
                window_match.group(1)
                if window_match
                else "configured"
            )

            meaning = (
                f"Standard deviation of the previous {window} observations; "
                "the rolling calculation is shifted by one observation "
                "to avoid using the current target and prevent data leakage."
            )
            feature_type = "Rolling Std"

        elif column == "day_of_week":
            meaning = (
                "Numeric day-of-week extracted from the date, "
                "where the value represents the weekday."
            )
            feature_type = "Calendar"

        elif column == "month":
            meaning = (
                "Numeric month extracted from the date."
            )
            feature_type = "Calendar"

        elif column == "day_of_month":
            meaning = (
                "Day of the month extracted from the date."
            )
            feature_type = "Calendar"

        elif column == "is_weekend":
            meaning = (
                "Binary indicator showing whether the date falls "
                "on a weekend."
            )
            feature_type = "Calendar"

        elif column == "is_month_start":
            meaning = (
                "Binary indicator showing whether the date is "
                "the first day of a month."
            )
            feature_type = "Calendar"

        elif column == "is_month_end":
            meaning = (
                "Binary indicator showing whether the date is "
                "the last day of a month."
            )
            feature_type = "Calendar"

        elif column == "is_holiday":
            meaning = (
                "Binary indicator showing whether the date is "
                "an Indian public holiday."
            )
            feature_type = "Holiday"

        elif "_x_" in column:
            components = column.split("_x_")

            meaning = (
                f"Interaction between {components[0]} and "
                f"{components[1]}."
                if len(components) == 2
                else "Interaction between the component features."
            )
            feature_type = "Interaction"

        else:
            raise ValueError(
                f"No catalog definition found for generated feature "
                f"'{column}'. Add an explicit catalog definition."
            )
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