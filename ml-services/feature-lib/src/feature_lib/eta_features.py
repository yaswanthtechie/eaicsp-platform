"""Point-in-time-correct ETA feature engineering."""

import pandas as pd
import numpy as np
from .asof_join import asof_join


def add_eta_features(
    shipments: pd.DataFrame,
) -> pd.DataFrame:
    """Add historical ETA and departure-time features to shipments.

    Historical features use only shipment outcomes that were available
    strictly before the current shipment's scheduled departure.

    Required columns:
        scheduled_pickup_date
        actual_delivery_date
        expected_delivery_date
        carrier_name
        route_id

    Optional column:
        actual_pickup_date

    Returns:
        A copy of the input DataFrame with ETA features added.
        Original row order and index are preserved.

    Notes:
        - Historical on-time rates use only completed shipments with
          known expected delivery dates.
        - Transit duration uses actual pickup when available, otherwise
          scheduled pickup.
        - Historical transit averages are calculated separately by
          carrier, route, and carrier-route combination.
        - Historical on-time rates are also calculated by departure
          weekday and departure season.
        - Historical outcomes are joined strictly before departure using
          asof_join().
        - Target/outcome columns such as transit_days and is_on_time
          are kept internal and are not returned.
    """
    if not isinstance(shipments, pd.DataFrame):
        raise TypeError("shipments must be a pandas DataFrame.")

    required_columns = [
        "scheduled_pickup_date",
        "actual_delivery_date",
        "expected_delivery_date",
        "carrier_name",
        "route_id",
    ]

    missing = [
        column
        for column in required_columns
        if column not in shipments.columns
    ]

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    result = shipments.copy()

    date_columns = [
        "scheduled_pickup_date",
        "actual_delivery_date",
        "expected_delivery_date",
    ]

    if "actual_pickup_date" in result.columns:
        date_columns.append("actual_pickup_date")

    for column in date_columns:
        # Normalise every date column to nanosecond precision so that
        # inputs mixing e.g. datetime64[us] (parquet) and datetime64[ns]
        # still pass asof_join's strict dtype check.
        result[column] = pd.to_datetime(
            result[column],
            errors="raise",
        ).dt.as_unit("ns")

    # ------------------------------------------------------------------
    # Departure calendar features
    # ------------------------------------------------------------------

    departure = result["scheduled_pickup_date"]

    result["departure_day_of_week"] = departure.dt.dayofweek
    result["departure_month"] = departure.dt.month

    month_to_season = {
        12: "winter",
        1: "winter",
        2: "winter",
        3: "summer",
        4: "summer",
        5: "summer",
        6: "monsoon",
        7: "monsoon",
        8: "monsoon",
        9: "monsoon",
        10: "post_monsoon",
        11: "post_monsoon",
    }

    result["departure_season"] = departure.dt.month.map(
        month_to_season
    )

    # ------------------------------------------------------------------
    # Internal historical outcome calculations
    # ------------------------------------------------------------------

    if "actual_pickup_date" in result.columns:
        transit_start = result["actual_pickup_date"].combine_first(
            result["scheduled_pickup_date"]
        )
    else:
        transit_start = result["scheduled_pickup_date"]

    result["__transit_days"] = (
        result["actual_delivery_date"] - transit_start
    ).dt.total_seconds() / 86400

    # Stored as columns (not separate Series) so every later filter is
    # positional and duplicate input index labels stay safe.
    result["__valid_transit"] = (
        result["__transit_days"].notna()
        & (result["__transit_days"] >= 0)
    )

    result["__valid_outcome"] = (
        result["actual_delivery_date"].notna()
        & result["expected_delivery_date"].notna()
    )

    # 1.0 = on time, 0.0 = late, NaN = outcome unknown.
    result["__on_time"] = (
        (result["actual_delivery_date"] <= result["expected_delivery_date"])
        .astype(float)
        .where(result["__valid_outcome"])
    )

    # Positional identifier preserves duplicate input indexes safely.
    result["__eta_position"] = range(len(result))

    # ------------------------------------------------------------------
    # Build cumulative historical statistics
    # ------------------------------------------------------------------

    def build_history(
        group_cols: list[str],
        rate_column: str | None,
        transit_column: str | None,
    ) -> pd.DataFrame:
        """Build cumulative historical statistics keyed by delivery time."""

        # On-time history needs a known outcome; transit history only needs
        # a valid transit time. Filter the two independently, so a delivered
        # shipment without an expected date still counts towards transit.
        usable = np.zeros(len(result), dtype=bool)

        if rate_column is not None:
            usable |= result["__valid_outcome"].to_numpy()

        if transit_column is not None:
            usable |= result["__valid_transit"].to_numpy()

        usable &= result["actual_delivery_date"].notna().to_numpy()
        usable &= result[group_cols].notna().all(axis=1).to_numpy()

        valid_history = result[usable].copy()

        if valid_history.empty:
            return pd.DataFrame()

        is_outcome = valid_history["__valid_outcome"].to_numpy()
        valid_history["__on_time_value"] = (
            valid_history["__on_time"].fillna(0.0).to_numpy()
        )
        valid_history["__outcome_count"] = is_outcome.astype(int)

        if transit_column is not None:
            is_transit = valid_history["__valid_transit"].to_numpy()
            valid_history["__transit_sum"] = np.where(
                is_transit,
                valid_history["__transit_days"].to_numpy(),
                0.0,
            )
            valid_history["__transit_count"] = is_transit.astype(int)

        # Multiple shipments can have the same delivery timestamp.
        # Aggregate them so asof_join has one feature record per
        # grouping key and timestamp.
        aggregation = {
            "__on_time_value": (
                "__on_time_value",
                "sum",
            ),
            "__outcome_count": (
                "__outcome_count",
                "sum",
            ),
        }

        if transit_column is not None:
            aggregation["__transit_sum"] = (
                "__transit_sum",
                "sum",
            )
            aggregation["__transit_count"] = (
                "__transit_count",
                "sum",
            )

        event = (
            valid_history
            .groupby(
                [*group_cols, "actual_delivery_date"],
                as_index=False,
                dropna=False,
            )
            .agg(**aggregation)
        )

        event = event.sort_values(
            [*group_cols, "actual_delivery_date"],
            kind="mergesort",
        )

        grouped = event.groupby(
            group_cols,
            sort=False,
            dropna=False,
        )

        # Cumulative values include the current delivery event.
        # asof_join() later performs a strict "< departure" join,
        # so an outcome occurring exactly at departure is excluded.
        event["__cumulative_on_time"] = (
            grouped["__on_time_value"].cumsum()
        )

        event["__cumulative_outcomes"] = (
            grouped["__outcome_count"].cumsum()
        )

        output_columns = [
            *group_cols,
            "actual_delivery_date",
        ]

        if transit_column is not None:
            event["__cumulative_transit_sum"] = (
                grouped["__transit_sum"].cumsum()
            )

            event["__cumulative_transit_count"] = (
                grouped["__transit_count"].cumsum()
            )

            event[transit_column] = (
                event["__cumulative_transit_sum"]
                / event["__cumulative_transit_count"].where(
                    event["__cumulative_transit_count"] > 0
                )
            )

            output_columns.append(transit_column)

        if rate_column is not None:
            event[rate_column] = (
                event["__cumulative_on_time"]
                / event["__cumulative_outcomes"].where(
                    event["__cumulative_outcomes"] > 0
                )
            )

            output_columns.append(rate_column)

        return event[output_columns].rename(
            columns={
                "actual_delivery_date": "__feature_time",
            }
        )

    # ------------------------------------------------------------------
    # Attach historical features using strict as-of joins
    # ------------------------------------------------------------------

    def attach_history(
        history: pd.DataFrame,
        group_cols: list[str],
        output_columns: list[str],
    ) -> None:
        """Attach historical values strictly before departure."""

        if history.empty:
            for column in output_columns:
                result[column] = float("nan")
            return

        valid_observations = result[
            result["scheduled_pickup_date"].notna()
            & result[group_cols].notna().all(axis=1)
        ].copy()

        if valid_observations.empty:
            for column in output_columns:
                result[column] = float("nan")
            return

        # Do not create output columns in result before this join.
        # Otherwise asof_join treats them as overlapping columns.
        joined = asof_join(
            valid_observations,
            history,
            observation_time="scheduled_pickup_date",
            feature_time="__feature_time",
            by=group_cols,
        )

        # Use positional arrays so duplicate DataFrame indexes remain safe.
        values = {
            column: [float("nan")] * len(result)
            for column in output_columns
        }

        for _, row in joined.iterrows():
            position = int(row["__eta_position"])

            for column in output_columns:
                values[column][position] = row[column]

        for column in output_columns:
            result[column] = values[column]

    # ------------------------------------------------------------------
    # Carrier history
    # ------------------------------------------------------------------

    carrier_history = build_history(
        group_cols=["carrier_name"],
        rate_column="historical_on_time_rate_carrier",
        transit_column="historical_avg_transit_days_carrier",
    )

    attach_history(
        carrier_history,
        group_cols=["carrier_name"],
        output_columns=[
            "historical_on_time_rate_carrier",
            "historical_avg_transit_days_carrier",
        ],
    )

    # ------------------------------------------------------------------
    # Route history
    # ------------------------------------------------------------------

    route_history = build_history(
        group_cols=["route_id"],
        rate_column="historical_on_time_rate_route",
        transit_column="historical_avg_transit_days_route",
    )

    attach_history(
        route_history,
        group_cols=["route_id"],
        output_columns=[
            "historical_on_time_rate_route",
            "historical_avg_transit_days_route",
        ],
    )

    # ------------------------------------------------------------------
    # Carrier + route history
    # ------------------------------------------------------------------

    carrier_route_history = build_history(
        group_cols=[
            "carrier_name",
            "route_id",
        ],
        rate_column=None,
        transit_column="historical_avg_transit_days_carrier_route",
    )

    attach_history(
        carrier_route_history,
        group_cols=[
            "carrier_name",
            "route_id",
        ],
        output_columns=[
            "historical_avg_transit_days_carrier_route",
        ],
    )

    # ------------------------------------------------------------------
    # Departure weekday historical on-time rate
    # ------------------------------------------------------------------

    weekday_history = build_history(
        group_cols=["departure_day_of_week"],
        rate_column="historical_on_time_rate_departure_day_of_week",
        transit_column=None,
    )

    attach_history(
        weekday_history,
        group_cols=["departure_day_of_week"],
        output_columns=[
            "historical_on_time_rate_departure_day_of_week",
        ],
    )

    # ------------------------------------------------------------------
    # Departure season historical on-time rate
    # ------------------------------------------------------------------

    season_history = build_history(
        group_cols=["departure_season"],
        rate_column="historical_on_time_rate_departure_season",
        transit_column=None,
    )

    attach_history(
        season_history,
        group_cols=["departure_season"],
        output_columns=[
            "historical_on_time_rate_departure_season",
        ],
    )

    # ------------------------------------------------------------------
    # Remove internal target/outcome columns
    # ------------------------------------------------------------------

    result = result.drop(
        columns=[
            "__transit_days",
            "__on_time",
            "__valid_transit",
            "__valid_outcome",
            "__eta_position",
        ]
    )

    return result