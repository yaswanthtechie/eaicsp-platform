
"""Feature preparation for R15 client shipment data."""

import pandas as pd


FEATURE_COLUMNS = [
    "dispatch_month",
    "dispatch_day_of_week",
    "distance_km",
    "weight_kg",
    "volume_m3",
]


def prepare_client_features(shipments: pd.DataFrame):
    """
    Prepare model features, target, and evaluation metadata.

    actual_delivery_date is used only to calculate the target.
    planned_delivery_date is used only for baseline evaluation.
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

    # Ensure dates are datetime values.
    date_columns = [
        "dispatch_date",
        "planned_delivery_date",
        "actual_delivery_date",
    ]
    for column in date_columns:
        data[column] = pd.to_datetime(
            data[column], format="mixed", errors="coerce"
        )

    # Calculate the target separately from model features.
    delivery_days = (
        data["actual_delivery_date"] - data["dispatch_date"]
    ).dt.total_seconds() / 86400

    valid_target = (
        data["dispatch_date"].notna()
        & data["actual_delivery_date"].notna()
        & delivery_days.gt(0)
    )

    diagnostics = {
        "total_shipments": len(data),
        "invalid_dispatch_date_count": int(data["dispatch_date"].isna().sum()),
        "invalid_actual_delivery_date_count": int(
            data["actual_delivery_date"].isna().sum()
        ),
        "non_positive_delivery_days_count": int(
            (
                data["dispatch_date"].notna()
                & data["actual_delivery_date"].notna()
                & delivery_days.le(0)
            ).sum()
        ),
        "excluded_target_rows": int((~valid_target).sum()),
    }

    data = data.loc[valid_target].copy()
    delivery_days = delivery_days.loc[valid_target]

    # Build model inputs. Actual and planned delivery dates are not included.
    X = pd.DataFrame(index=data.index)

    X["dispatch_month"] = data["dispatch_date"].dt.month
    X["dispatch_day_of_week"] = data["dispatch_date"].dt.dayofweek

    for column in ["distance_km", "weight_kg", "volume_m3"]:
        X[column] = pd.to_numeric(
            data[column], errors="coerce"
        ).replace(
            [float("inf"), float("-inf")],
            float("nan"),
        )

    X = X[FEATURE_COLUMNS]

    # Metadata is kept separate from the model feature matrix.
    planned_days = (
        data["planned_delivery_date"] - data["dispatch_date"]
    ).dt.total_seconds() / 86400

    planned_days = planned_days.where(planned_days.gt(0))

    metadata = pd.DataFrame(
        {
            "shipment_id": data["shipment_id"],
            "carrier_name": data["carrier_name"],
            "dispatch_date": data["dispatch_date"],
            "planned_delivery_days": planned_days,
        },
        index=data.index,
    )

    y = delivery_days.rename("delivery_days")

    diagnostics["prepared_shipments"] = len(X)
    diagnostics["missing_distance_count"] = int(X["distance_km"].isna().sum())
    diagnostics["missing_weight_count"] = int(X["weight_kg"].isna().sum())
    diagnostics["missing_volume_count"] = int(X["volume_m3"].isna().sum())
    diagnostics["missing_planned_baseline_count"] = int(
        metadata["planned_delivery_days"].isna().sum()
    )

    return (
        X.reset_index(drop=True),
        y.reset_index(drop=True),
        metadata.reset_index(drop=True),
        diagnostics,
    )
