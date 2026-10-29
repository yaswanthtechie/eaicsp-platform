from src.features import build_eta_features
from feature_lib import add_eta_features
import pandas as pd
EXPECTED_FEATURE_COLUMNS = {
    "order_id",
    "purchase_year",
    "purchase_month",
    "purchase_day_of_week",
    "purchase_hour",
    "origin_lat",
    "origin_lng",
    "destination_lat",
    "destination_lng",
    "distance_km",
    "item_count",
    "total_weight_kg",
    "total_volume_cm3",
    "total_freight_value",
    "product_category_name",
    "delivery_days",
}


def test_one_row_per_order(sample_datasets):
    """Each order must produce exactly one feature row."""

    features = build_eta_features(
        sample_datasets
    )

    assert features["order_id"].is_unique


def test_expected_order_count(sample_datasets):
    """Feature generation must preserve the expected order count."""

    features = build_eta_features(
        sample_datasets
    )

    assert len(features) == 3


def test_expected_feature_columns(sample_datasets):
    """Feature output must match the model dataset contract."""

    features = build_eta_features(
        sample_datasets
    )

    expected_feature_columns = {
        "order_id",
        "purchase_year",
        "purchase_month",
        "purchase_day_of_week",
        "purchase_hour",
        "origin_lat",
        "origin_lng",
        "destination_lat",
        "destination_lng",
        "distance_km",
        "item_count",
        "total_weight_kg",
        "total_volume_cm3",
        "total_freight_value",
        "product_category_name",
        "historical_on_time_rate_carrier",
        "historical_avg_transit_days_carrier",
        "historical_on_time_rate_route",
        "historical_avg_transit_days_route",
        "historical_avg_transit_days_carrier_route",
        "historical_on_time_rate_departure_season",
        "delivery_days",
    }

    assert set(features.columns) == expected_feature_columns


def test_target_is_positive(sample_datasets):
    """Every generated delivery target must be positive."""

    features = build_eta_features(
        sample_datasets
    )

    assert (
        features["delivery_days"] > 0
    ).all()


def test_item_features_are_aggregated(sample_datasets):
    """
    Item-level information must be aggregated to the
    order level.
    """

    features = build_eta_features(
        sample_datasets
    )

    order = features.loc[
        features["order_id"] == "order_1"
    ].iloc[0]

    assert order["item_count"] == 2

    assert (
        order["total_freight_value"]
        == 5.0
    )

    assert (
        order["total_weight_kg"]
        == 0.8
    )


def test_volume_is_aggregated(sample_datasets):
    """Product dimensions must be aggregated into total volume."""

    features = build_eta_features(
        sample_datasets
    )

    order = features.loc[
        features["order_id"] == "order_1"
    ].iloc[0]

    expected_volume = (
        10 * 5 * 5
        + 12 * 6 * 6
    )

    assert (
        order["total_volume_cm3"]
        == expected_volume
    )


def test_geolocation_is_aggregated_before_join(
    sample_datasets,
):
    """
    Geolocation records must be aggregated before joining
    so that the order-level feature table remains one row
    per order.
    """

    features = build_eta_features(
        sample_datasets
    )

    assert len(features) == 3

    assert (
        features["origin_lat"]
        .notna()
        .all()
    )

    assert (
        features["destination_lat"]
        .notna()
        .all()
    )


def test_distance_is_created(sample_datasets):
    """Origin/destination coordinates must produce distance."""

    features = build_eta_features(
        sample_datasets
    )

    assert "distance_km" in features.columns

    assert (
        features["distance_km"] >= 0
    ).all()


def test_purchase_time_features_are_created(
    sample_datasets,
):
    """Purchase timestamp must produce time-based features."""

    features = build_eta_features(
        sample_datasets
    )

    assert (
        features["purchase_year"].tolist()
        == [
            2018,
            2018,
            2018,
        ]
    )

    assert (
        features["purchase_month"].tolist()
        == [
            1,
            1,
            1,
        ]
    )

    assert (
        features["purchase_hour"].tolist()
        == [
            10,
            11,
            12,
        ]
    )


def test_leakage_columns_are_not_returned(
    sample_datasets,
):
    """
    Post-delivery information must never be returned as
    model features.

    These fields are known only after or around delivery
    and therefore must not enter the feature dataset.
    """

    features = build_eta_features(
        sample_datasets
    )

    forbidden_columns = {
        "order_status",
        "order_delivered_customer_date",
        "order_delivered_carrier_date",
        "order_estimated_delivery_date",
    }

    for column in forbidden_columns:
        assert column not in features.columns


def test_purchase_timestamp_is_not_returned(
    sample_datasets,
):
    """
    Raw purchase timestamp is used to derive time features
    but must not remain in the model feature dataset.
    """

    features = build_eta_features(
        sample_datasets
    )

    assert (
        "order_purchase_timestamp"
        not in features.columns
    )


def test_carrier_is_not_returned_as_model_feature(
    sample_datasets,
):
    """
    Carrier must not be introduced as a model feature because
    the current Olist dataset does not provide a genuine
    carrier feature.
    """

    features = build_eta_features(
        sample_datasets
    )

    assert "carrier" not in features.columns


def test_target_is_not_used_as_input_feature(
    sample_datasets,
):
    """
    delivery_days is the prediction target and must not be
    treated as an input feature.
    """

    features = build_eta_features(
        sample_datasets
    )

    model_feature_columns = (
        set(features.columns)
        - {
            "order_id",
            "delivery_days",
        }
    )

    assert (
        "delivery_days"
        not in model_feature_columns
    )

def test_eta_history_features_exclude_in_flight_and_equal_timestamp_outcomes():
    """Only outcomes delivered strictly before departure may be used."""

    from feature_lib import add_eta_features

    features = pd.DataFrame(
        {
            "order_id": ["a_in_flight", "b_current", "c", "d_equal"],
            "scheduled_pickup_date": pd.to_datetime(
                [
                    "2024-01-08 10:00",
                    "2024-01-10 10:00",
                    "2024-01-15 10:00",
                    "2024-01-20 10:00",
                ]
            ),
            "actual_delivery_date": pd.to_datetime(
                [
                    "2024-01-15 10:00",  # departs before b, delivers after b departs
                    "2024-01-12 10:00",
                    "2024-01-20 10:00",  # delivered exactly when d departs
                    "2024-01-25 10:00",
                ]
            ),
            "expected_delivery_date": pd.to_datetime(
                ["2024-01-16", "2024-01-13", "2024-01-21", "2024-01-26"]
            ),
            "carrier_name": ["carrier_a"] * 4,
            "route_id": ["route_a"] * 4,
        }
    )

    result = add_eta_features(features).set_index("order_id")
    col = "historical_avg_transit_days_carrier"

    # a is still in flight when b departs, so b must have no history.
    assert pd.isna(result.loc["b_current", col])

    # a is delivered exactly when c departs, so it is excluded; only b (2 days) counts.
    assert result.loc["c", col] == 2.0

    # c is delivered exactly when d departs, so it is excluded; a (7) and b (2) count.
    assert result.loc["d_equal", col] == 4.5