
"""Feature preparation for R15 client shipment data."""

import pandas as pd


FEATURE_COLUMNS = [
    "dispatch_month",
    "dispatch_day_of_week",
    "distance_km",
    "weight_kg",
    "volume_m3",
    "planned_delivery_days",
]

CATEGORICAL_COLUMNS = [
    "carrier_name",
]


def prepare_client_features(shipments: pd.DataFrame):
    """
    Prepare model features, target, and evaluation metadata.

    actual_delivery_date is used to calculate the target and is
    retained in metadata for chronological label-purging.

    planned_delivery_date is known at dispatch time, so its duration
    from dispatch is included as a model feature and baseline input.
    """

    required_columns = {
        "shipment_id",
        "carrier_name",
        "dispatch_date",
        "planned_delivery_date",
        "actual_delivery_date",
        "distance_km",
        "weight_kg",
        "volume_m3",
    }

    missing = required_columns - set(shipments.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    data = shipments.copy()

    date_columns = [
        "dispatch_date",
        "planned_delivery_date",
        "actual_delivery_date",
    ]

    # Strictly accept YYYY-MM-DD dates.
    # Invalid dates become NaT and are handled by diagnostics.
    for column in date_columns:
        data[column] = pd.to_datetime(
            data[column],
            format="%Y-%m-%d",
            errors="coerce",
        )

    delivery_days = (
        data["actual_delivery_date"] - data["dispatch_date"]
    ).dt.total_seconds() / 86400

    # Same-day deliveries (0 days) are valid.
    valid_target = (
        data["dispatch_date"].notna()
        & data["actual_delivery_date"].notna()
        & delivery_days.ge(0)
    )

    diagnostics = {
        "total_shipments": len(data),
        "invalid_dispatch_date_count": int(
            data["dispatch_date"].isna().sum()
        ),
        "invalid_actual_delivery_date_count": int(
            data["actual_delivery_date"].isna().sum()
        ),
        "negative_delivery_days_count": int(
            (
                data["dispatch_date"].notna()
                & data["actual_delivery_date"].notna()
                & delivery_days.lt(0)
            ).sum()
        ),
        "excluded_target_rows": int((~valid_target).sum()),
    }

    data = data.loc[valid_target].copy()
    delivery_days = delivery_days.loc[valid_target]

    planned_days = (
        data["planned_delivery_date"] - data["dispatch_date"]
    ).dt.total_seconds() / 86400

    # Zero-day planned delivery is also valid.
    planned_days = planned_days.where(planned_days.ge(0))

    # Build numeric model inputs.
    X = pd.DataFrame(index=data.index)

    X["dispatch_month"] = data["dispatch_date"].dt.month
    X["dispatch_day_of_week"] = data["dispatch_date"].dt.dayofweek

    for column in ["distance_km", "weight_kg", "volume_m3"]:
        X[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        ).replace(
            [float("inf"), float("-inf")],
            float("nan"),
        )

    X["planned_delivery_days"] = planned_days

    # Carrier is a categorical input and will be encoded in the pipeline.
    X["carrier_name"] = data["carrier_name"].fillna("Unknown")

    X = X[FEATURE_COLUMNS + CATEGORICAL_COLUMNS]

    # Metadata is separate from model features.
    metadata = pd.DataFrame(
        {
            "shipment_id": data["shipment_id"],
            "carrier_name": data["carrier_name"],
            "dispatch_date": data["dispatch_date"],
            "actual_delivery_date": data["actual_delivery_date"],
            "planned_delivery_days": planned_days,
        },
        index=data.index,
    )

    y = delivery_days.rename("delivery_days")

    diagnostics["prepared_shipments"] = len(X)
    diagnostics["missing_distance_count"] = int(
        X["distance_km"].isna().sum()
    )
    diagnostics["missing_weight_count"] = int(
        X["weight_kg"].isna().sum()
    )
    diagnostics["missing_volume_count"] = int(
        X["volume_m3"].isna().sum()
    )
    diagnostics["missing_planned_baseline_count"] = int(
        metadata["planned_delivery_days"].isna().sum()
    )

    return (
        X.reset_index(drop=True),
        y.reset_index(drop=True),
        metadata.reset_index(drop=True),
        diagnostics,
    )
