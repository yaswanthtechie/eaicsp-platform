"""
R15-H2 features: only what is known when a seed shipment is dispatched.

Training uses Olist orders, measured from the moment the seller handed
the parcel to the carrier (order_delivered_carrier_date) to customer
delivery. That matches the eta.shipment.predicted contract, where
eta_days is counted from dispatched_at.
"""

import numpy as np
import pandas as pd

from .features import (
    TARGET_COLUMN,
    _parse_order_dates,
    build_eta_features,
)


H2_FEATURES = [
    "dispatch_month",
    "dispatch_day_of_week",
    "distance_km",
]


def add_dispatch_time_features(frame, dispatched_at):
    """Add dispatch-time features from a datetime Series."""

    dispatched_at = pd.to_datetime(
        pd.Series(dispatched_at)
    ).reset_index(drop=True)

    frame = frame.reset_index(drop=True).copy()
    frame["dispatch_month"] = dispatched_at.dt.month
    frame["dispatch_day_of_week"] = dispatched_at.dt.dayofweek

    return frame


def build_h2_features(datasets):
    """
    Build the H2 training dataset from raw Olist data.

    Target: days from carrier hand-off to customer delivery.
    Features: dispatch month, dispatch weekday, seller -> customer
    distance. Nothing else is available for a seed shipment.
    """

    # Reuse the R14 extraction for the distance only.
    distance = build_eta_features(datasets)[
        ["order_id", "distance_km"]
    ]

    orders = _parse_order_dates(datasets["orders"])[
        [
            "order_id",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
        ]
    ]

    h2 = distance.merge(
        orders,
        on="order_id",
        how="left",
        validate="one_to_one",
    )

    dispatched_at = h2["order_delivered_carrier_date"]

    h2[TARGET_COLUMN] = (
        h2["order_delivered_customer_date"] - dispatched_at
    ).dt.total_seconds() / 86400.0

    h2 = add_dispatch_time_features(h2, dispatched_at)

    # Olist has orders with no carrier date, and a few where the
    # carrier date is after delivery. Neither is a usable target.
    h2 = h2.dropna(subset=[*H2_FEATURES, TARGET_COLUMN])
    h2 = h2[h2[TARGET_COLUMN] > 0]

    return h2[
        ["order_id", *H2_FEATURES, TARGET_COLUMN]
    ].reset_index(drop=True)


def apply_interval(predictions, calibration):
    """Turn point predictions into [low, high] using the calibration."""

    residual_lower = float(calibration["residual_lower"])
    residual_upper = float(calibration["residual_upper"])

    if residual_lower > residual_upper:
        raise ValueError(
            "H2 prediction interval calibration is invalid: "
            "lower residual exceeds upper residual."
        )

    predictions = np.asarray(predictions, dtype=float)
    low = np.maximum(0.0, predictions + residual_lower)
    high = np.maximum(low, predictions + residual_upper)

    return low, high