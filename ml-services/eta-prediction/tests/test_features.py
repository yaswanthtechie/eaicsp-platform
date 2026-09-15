from src.features import build_eta_features


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

    assert set(features.columns) == (
        EXPECTED_FEATURE_COLUMNS
    )


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