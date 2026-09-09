import pandas as pd
import pytest

from src.preprocess import (
    MODEL_FEATURES,
    preprocess_features,
    validate_columns,
    validate_order_ids,
    validate_target,
)


def make_valid_features():
    """Create a minimal valid preprocessed feature dataset."""

    return pd.DataFrame(
        {
            "order_id": ["order_1", "order_2"],
            "purchase_year": [2018, 2018],
            "purchase_month": [1, 1],
            "purchase_day_of_week": [0, 1],
            "purchase_hour": [10, 11],
            "origin_lat": [-23.55, -22.90],
            "origin_lng": [-46.63, -43.18],
            "destination_lat": [-23.56, -22.91],
            "destination_lng": [-46.65, -43.20],
            "distance_km": [5.0, 10.0],
            "item_count": [1, 2],
            "total_weight_kg": [0.5, 1.0],
            "total_volume_cm3": [100.0, 200.0],
            "total_freight_value": [5.0, 10.0],
            "product_category_name": [
                "electronics",
                "books",
            ],
            "delivery_days": [5.0, 8.0],
        }
    )


def test_valid_features_pass_preprocessing():
    features = make_valid_features()

    result = preprocess_features(features)

    assert len(result) == 2
    assert result["order_id"].is_unique
    assert result["delivery_days"].notna().all()


def test_missing_category_is_replaced_with_unknown():
    features = make_valid_features()

    features.loc[
        0,
        "product_category_name",
    ] = None

    result = preprocess_features(features)

    assert (
        result.loc[
            result["order_id"] == "order_1",
            "product_category_name",
        ].iloc[0]
        == "unknown"
    )


def test_missing_numeric_feature_removes_row():
    features = make_valid_features()

    features.loc[
        0,
        "distance_km",
    ] = None

    result = preprocess_features(features)

    assert len(result) == 1
    assert result["order_id"].iloc[0] == "order_2"


def test_multiple_missing_numeric_features_remove_row():
    features = make_valid_features()

    features.loc[
        0,
        "origin_lat",
    ] = None

    features.loc[
        1,
        "total_weight_kg",
    ] = None

    result = preprocess_features(features)

    assert len(result) == 0


def test_duplicate_order_id_raises_error():
    features = make_valid_features()

    features.loc[
        1,
        "order_id",
    ] = "order_1"

    with pytest.raises(
        ValueError,
        match="Duplicate order_id",
    ):
        validate_order_ids(features)


def test_missing_order_id_raises_error():
    features = make_valid_features()

    features.loc[
        0,
        "order_id",
    ] = None

    with pytest.raises(
        ValueError,
        match="order_id contains missing values",
    ):
        validate_order_ids(features)


def test_missing_required_column_raises_error():
    features = make_valid_features()

    features = features.drop(
        columns=["distance_km"]
    )

    with pytest.raises(
        ValueError,
        match="Missing required columns",
    ):
        validate_columns(features)


def test_missing_target_raises_error():
    features = make_valid_features()

    features.loc[
        0,
        "delivery_days",
    ] = None

    with pytest.raises(
        ValueError,
        match="delivery_days contains missing values",
    ):
        validate_target(features)


def test_non_positive_target_raises_error():
    features = make_valid_features()

    features.loc[
        0,
        "delivery_days",
    ] = 0

    with pytest.raises(
        ValueError,
        match="Invalid delivery_days values",
    ):
        validate_target(features)


def test_negative_target_raises_error():
    features = make_valid_features()

    features.loc[
        0,
        "delivery_days",
    ] = -1

    with pytest.raises(
        ValueError,
        match="Invalid delivery_days values",
    ):
        validate_target(features)


def test_all_model_features_are_preserved():
    features = make_valid_features()

    result = preprocess_features(features)

    for column in MODEL_FEATURES:
        assert column in result.columns


def test_preprocessing_removes_all_model_missing_values():
    features = make_valid_features()

    features.loc[
        0,
        "product_category_name",
    ] = None

    features.loc[
        1,
        "distance_km",
    ] = None

    result = preprocess_features(features)

    assert result["product_category_name"].isna().sum() == 0
    assert result[MODEL_FEATURES].isna().sum().sum() == 0