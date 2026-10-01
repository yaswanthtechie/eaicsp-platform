
"""Point-in-time-correct ETA feature engineering."""

import pandas as pd


def add_eta_features(
    shipments: pd.DataFrame,
) -> pd.DataFrame:
    """Add historical ETA and departure-time features to shipments.

    Historical features use only shipments whose delivery outcomes
    were available strictly before the current shipment's departure.

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
        - Historical rates exclude shipments with missing expected dates.
        - Transit duration uses actual pickup when available, otherwise
          scheduled pickup.
        - Historical transit averages are calculated separately by
          carrier, route, and carrier-route combination.
        - Rows without eligible historical data receive missing values.
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
        result[column] = pd.to_datetime(
            result[column],
            errors="coerce",
        )

    # Departure calendar features.
    departure = result["scheduled_pickup_date"]
    result["departure_day_of_week"] = departure.dt.dayofweek
    result["departure_month"] = departure.dt.month

    # Meteorological-style seasons for the Northern Hemisphere:
    # Dec-Feb = winter, Mar-May = spring, Jun-Aug = summer,
    # Sep-Nov = autumn.
    month_to_season = {
        12: "winter",
        1: "winter",
        2: "winter",
        3: "spring",
        4: "spring",
        5: "spring",
        6: "summer",
        7: "summer",
        8: "summer",
        9: "autumn",
        10: "autumn",
        11: "autumn",
    }
    result["departure_season"] = departure.dt.month.map(
        month_to_season
    )

    # Determine the transit start date. Prefer actual pickup when
    # present; otherwise use scheduled pickup as a fallback.
    if "actual_pickup_date" in result.columns:
        transit_start = result["actual_pickup_date"].combine_first(
            result["scheduled_pickup_date"]
        )
    else:
        transit_start = result["scheduled_pickup_date"]

    result["transit_days"] = (
        result["actual_delivery_date"] - transit_start
    ).dt.total_seconds() / 86400

    # A delivery outcome is known only when both actual and expected
    # delivery dates are available.
    valid_outcome = (
        result["actual_delivery_date"].notna()
        & result["expected_delivery_date"].notna()
    )

    result["is_on_time"] = pd.Series(
        pd.NA,
        index=result.index,
        dtype="Float64",
    )
    result.loc[valid_outcome, "is_on_time"] = (
        result.loc[valid_outcome, "actual_delivery_date"]
        <= result.loc[valid_outcome, "expected_delivery_date"]
    ).astype(float)

    # Preallocate output values in row order. This also preserves
    # the original DataFrame index, including duplicate index labels.
    carrier_on_time_rates = []
    route_on_time_rates = []
    carrier_avg_transit = []
    route_avg_transit = []
    carrier_route_avg_transit = []

    # Iterate positionally so duplicate DataFrame indices are safe.
    for position in range(len(result)):
        shipment = result.iloc[position]
        current_departure = shipment["scheduled_pickup_date"]

        # No departure timestamp means no valid point-in-time history
        # or departure calendar context for this row.
        if pd.isna(current_departure):
            carrier_on_time_rates.append(float("nan"))
            route_on_time_rates.append(float("nan"))
            carrier_avg_transit.append(float("nan"))
            route_avg_transit.append(float("nan"))
            carrier_route_avg_transit.append(float("nan"))
            continue

        # Only outcomes completed strictly before this departure
        # can contribute to historical features.
        eligible = (
            result["actual_delivery_date"].notna()
            & (result["actual_delivery_date"] < current_departure)
            & result["scheduled_pickup_date"].notna()
            & (result["scheduled_pickup_date"] < current_departure)
        )

        previous = result.loc[eligible]

        carrier = shipment["carrier_name"]
        route = shipment["route_id"]

        # Avoid matching missing grouping values to one another.
        if pd.isna(carrier):
            carrier_history = previous.iloc[0:0]
        else:
            carrier_history = previous.loc[
                previous["carrier_name"].eq(carrier)
            ]

        if pd.isna(route):
            route_history = previous.iloc[0:0]
        else:
            route_history = previous.loc[
                previous["route_id"].eq(route)
            ]

        if pd.isna(carrier) or pd.isna(route):
            carrier_route_history = previous.iloc[0:0]
        else:
            carrier_route_history = previous.loc[
                previous["carrier_name"].eq(carrier)
                & previous["route_id"].eq(route)
            ]

        # Historical on-time rates use only records with known
        # on-time outcomes.
        carrier_outcomes = carrier_history["is_on_time"].dropna()
        route_outcomes = route_history["is_on_time"].dropna()

        carrier_on_time_rates.append(
            carrier_outcomes.mean()
            if not carrier_outcomes.empty
            else float("nan")
        )
        route_on_time_rates.append(
            route_outcomes.mean()
            if not route_outcomes.empty
            else float("nan")
        )

        # Transit averages use only completed shipments with a
        # valid, non-negative transit duration.
        carrier_transit = carrier_history["transit_days"].dropna()
        route_transit = route_history["transit_days"].dropna()
        carrier_route_transit = (
            carrier_route_history["transit_days"].dropna()
        )

        carrier_transit = carrier_transit[carrier_transit >= 0]
        route_transit = route_transit[route_transit >= 0]
        carrier_route_transit = carrier_route_transit[
            carrier_route_transit >= 0
        ]

        carrier_avg_transit.append(
            carrier_transit.mean()
            if not carrier_transit.empty
            else float("nan")
        )
        route_avg_transit.append(
            route_transit.mean()
            if not route_transit.empty
            else float("nan")
        )
        carrier_route_avg_transit.append(
            carrier_route_transit.mean()
            if not carrier_route_transit.empty
            else float("nan")
        )

    result["historical_on_time_rate_carrier"] = (
        carrier_on_time_rates
    )
    result["historical_on_time_rate_route"] = (
        route_on_time_rates
    )
    result["historical_avg_transit_days_carrier"] = (
        carrier_avg_transit
    )
    result["historical_avg_transit_days_route"] = (
        route_avg_transit
    )
    result["historical_avg_transit_days_carrier_route"] = (
        carrier_route_avg_transit
    )

    return result