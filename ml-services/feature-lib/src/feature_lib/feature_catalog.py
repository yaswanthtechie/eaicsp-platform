import re

from .build_features import FEATURE_VERSIONS, build_all_features

import pandas as pd

from .sensor_features import add_sensor_features

from .eta_features import add_eta_features


STD_DESCRIPTIONS = {
    1: "Sample standard deviation (ddof=1)",
    0: "Population standard deviation (ddof=0)",
}


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

    std_ddof = FEATURE_VERSIONS[feature_version]["roll_std_ddof"]
    std_kind = STD_DESCRIPTIONS[std_ddof]

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
                f"{std_kind} of the previous {window} observations; "
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

        catalog.append(
            {
                "feature": column,
                "type": feature_type,
                "meaning": meaning,
                "version": feature_version,
            }
        )

    return pd.DataFrame(catalog)


def generate_sensor_feature_catalog(
    df: pd.DataFrame,
    sensor_cols: list[str],
    timestamp_col: str,
    window: int = 7,
    group_cols: list[str] | None = None,
    sensor_pairs: list[tuple[str, str]] | None = None,
) -> pd.DataFrame:
    """
    Generate a human-readable catalog of sensor features.

    Rolling statistics use previous observations only.

    The rolling window represents a number of historical observations,
    not a fixed elapsed-time duration.

    Current sensor readings are used for z-scores,
    rate of change, and cross-sensor ratios.
    """

    features = add_sensor_features(
        df=df,
        sensor_cols=sensor_cols,
        timestamp_col=timestamp_col,
        window=window,
        group_cols=group_cols,
        sensor_pairs=sensor_pairs,
    )

    catalog = []

    for column in features.columns:
        if column in df.columns:
            continue

        if column.endswith("_rolling_zscore_" + str(window)):
            sensor = column.removesuffix(
                f"_rolling_zscore_{window}"
            )

            meaning = (
                f"Current {sensor} reading standardized against "
                f"the previous {window} readings using the "
                "historical rolling mean and standard deviation. "
                "The baseline excludes the current reading."
            )

            feature_type = "Sensor Rolling Z-Score"

        elif column.endswith("_rate_of_change"):
            sensor = column.removesuffix("_rate_of_change")

            meaning = (
                f"Relative change in the current {sensor} reading "
                "compared with its previous reading. "
                "A zero previous reading produces NaN."
            )

            feature_type = "Sensor Rate of Change"

        elif column.endswith("_rolling_min_" + str(window)):
            sensor = column.removesuffix(
                f"_rolling_min_{window}"
            )

            meaning = (
                f"Minimum {sensor} value across the previous "
                f"{window} readings, excluding the current reading."
            )

            feature_type = "Sensor Rolling Min"

        elif column.endswith("_rolling_max_" + str(window)):
            sensor = column.removesuffix(
                f"_rolling_max_{window}"
            )

            meaning = (
                f"Maximum {sensor} value across the previous "
                f"{window} readings, excluding the current reading."
            )

            feature_type = "Sensor Rolling Max"

        elif column.endswith("_to_" + sensor_cols[-1] + "_ratio"):
            numerator, denominator = column.removesuffix(
                "_ratio"
            ).split("_to_", 1)

            meaning = (
                f"Current {numerator} reading divided by current "
                f"{denominator} reading. A zero denominator "
                "produces NaN."
            )

            feature_type = "Cross-Sensor Ratio"

        elif "_to_" in column and column.endswith("_ratio"):
            numerator, denominator = column.removesuffix(
                "_ratio"
            ).split("_to_", 1)

            meaning = (
                f"Current {numerator} reading divided by current "
                f"{denominator} reading. A zero denominator "
                "produces NaN."
            )

            feature_type = "Cross-Sensor Ratio"

        else:
            raise ValueError(
                f"No sensor catalog definition found for "
                f"generated feature '{column}'."
            )

        catalog.append(
            {
                "feature": column,
                "type": feature_type,
                "meaning": meaning,
                "version": "sensor-v1",
            }
        )

    return pd.DataFrame(
        catalog,
        columns=["feature", "type", "meaning", "version"],
    )


def generate_eta_feature_catalog(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Generate a human-readable catalog of ETA features."""

    features = add_eta_features(df)

    eta_definitions = {
        "departure_day_of_week": (
            "ETA Calendar",
            "Day of the week of the scheduled shipment departure "
            "(Monday=0, Sunday=6)."
        ),
        "departure_month": (
            "ETA Calendar",
            "Month of the scheduled shipment departure (1-12)."
        ),
        "departure_season": (
            "ETA Calendar",
            "Season derived from the scheduled departure month."
        ),
        "historical_on_time_rate_carrier": (
            "ETA Historical",
            "Proportion of previously completed shipments for the "
            "same carrier delivered on or before their expected date. "
            "Only outcomes available before departure are included."
        ),
        "historical_on_time_rate_route": (
            "ETA Historical",
            "Proportion of previously completed shipments for the "
            "same route delivered on or before their expected date. "
            "Only outcomes available before departure are included."
        ),
        "historical_on_time_rate_departure_day_of_week": (
            "ETA Historical",
            "Proportion of previously completed shipments with the "
            "same departure weekday that were delivered on or before "
            "their expected date. Only outcomes available before "
            "departure are included."
        ),
        "historical_on_time_rate_departure_season": (
            "ETA Historical",
            "Proportion of previously completed shipments with the "
            "same departure season that were delivered on or before "
            "their expected date. Only outcomes available before "
            "departure are included."
        ),
        "historical_avg_transit_days_carrier": (
            "ETA Historical",
            "Average transit duration in days for previously completed "
            "shipments handled by the same carrier."
        ),
        "historical_avg_transit_days_route": (
            "ETA Historical",
            "Average transit duration in days for previously completed "
            "shipments on the same route."
        ),
        "historical_avg_transit_days_carrier_route": (
            "ETA Historical",
            "Average transit duration in days for previously completed "
            "shipments with the same carrier and route."
        ),
    }

    catalog = []

    for column, (feature_type, meaning) in eta_definitions.items():
        if column in features.columns and column not in df.columns:
            catalog.append(
                {
                    "feature": column,
                    "type": feature_type,
                    "meaning": meaning,
                    "version": "eta-v1",
                }
            )

    return pd.DataFrame(
        catalog,
        columns=["feature", "type", "meaning", "version"],
    )