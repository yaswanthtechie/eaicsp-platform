import numpy as np
import pytest

from src.model_loader import (
    _calculate_distance,
    _lookup_city_coordinates,
    _validate_payload,
    load_model,
    prepare_prediction_input,
)
from src.predict import predict


def _valid_payload():
    """Return a valid city-based logistics-service payload."""

    return {
        "origin": "city_a",
        "destination": "city_b",
        "carrier": "proxy-carrier",
        "weight_kg": 2.5,
    }


def test_model_loader_and_prediction_lifecycle(
    trained_model_path,
    patch_city_coordinates,
):
    """
    Test the complete model-loader and prediction lifecycle.

    The trained_model_path fixture creates a temporary trained
    pipeline, while patch_city_coordinates supplies synthetic
    city coordinates so the test does not depend on the real
    Olist geolocation CSV.
    """

    assert trained_model_path.exists()

    model = load_model()

    assert model is not None
    assert hasattr(model, "predict")

    payload = _valid_payload()

    features = prepare_prediction_input(
        payload
    )

    assert len(features) == 1

    expected_columns = {
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
    }

    assert set(features.columns) == (
        expected_columns
    )

    # Carrier is accepted at service level but is not
    # a model feature.
    assert "carrier" not in features.columns

    origin_lat, origin_lng = (
        _lookup_city_coordinates(
            payload["origin"]
        )
    )

    destination_lat, destination_lng = (
        _lookup_city_coordinates(
            payload["destination"]
        )
    )

    row = features.iloc[0]

    assert np.isclose(
        row["origin_lat"],
        origin_lat,
    )

    assert np.isclose(
        row["origin_lng"],
        origin_lng,
    )

    assert np.isclose(
        row["destination_lat"],
        destination_lat,
    )

    assert np.isclose(
        row["destination_lng"],
        destination_lng,
    )

    assert (
        row["total_weight_kg"]
        == payload["weight_kg"]
    )

    assert (
        row["product_category_name"]
        == "unknown"
    )

    assert (
        row["item_count"]
        == 1
    )

    assert (
        row["total_volume_cm3"]
        == 0.0
    )

    assert (
        row["total_freight_value"]
        == 0.0
    )

    expected_distance = _calculate_distance(
        origin_lat,
        origin_lng,
        destination_lat,
        destination_lng,
    )

    assert np.isclose(
        row["distance_km"],
        expected_distance,
    )

    assert row["distance_km"] > 0

    assert np.isfinite(
        row["distance_km"]
    )

    prediction = model.predict(
        features
    )

    assert len(prediction) == 1

    assert np.isfinite(
        prediction
    ).all()

    assert np.issubdtype(
        prediction.dtype,
        np.number,
    )

    assert prediction[0] >= 0


def test_predict_returns_exact_contract(
    trained_model_path,
    patch_city_coordinates,
):
    """
    Verify the public predict() function follows the exact
    city-based logistics-service contract required by Round 4.

    The prediction must contain:
        eta_days
        confidence_low
        confidence_high

    The point prediction is not required to lie inside the
    empirical prediction interval because calibration may be
    asymmetric.
    """

    assert trained_model_path.exists()

    payload = _valid_payload()

    result = predict(
        payload
    )

    assert set(result.keys()) == {
        "eta_days",
        "confidence_low",
        "confidence_high",
    }

    assert isinstance(
        result["eta_days"],
        float,
    )

    assert np.isfinite(
        result["eta_days"]
    )

    assert result["eta_days"] >= 0

    assert isinstance(
        result["confidence_low"],
        float,
    )

    assert isinstance(
        result["confidence_high"],
        float,
    )

    assert np.isfinite(
        result["confidence_low"]
    )

    assert np.isfinite(
        result["confidence_high"]
    )

    assert (
        result["confidence_low"]
        <= result["confidence_high"]
    )

    assert (
        result["confidence_low"]
        >= 0
    )

    assert (
        result["confidence_high"]
        >= 0
    )


def test_asymmetric_prediction_interval_is_accepted(
    monkeypatch,
):
    """
    Verify that a legitimate asymmetric empirical prediction
    interval is accepted even when the lower confidence bound
    is above the point prediction.
    """

    class DummyModel:
        """Return a deterministic ETA prediction."""

        def predict(self, features):
            return np.array(
                [10.0]
            )

    monkeypatch.setattr(
        "src.predict.prepare_prediction_input",
        lambda payload: None,
    )

    monkeypatch.setattr(
        "src.predict.load_model",
        lambda: DummyModel(),
    )

    monkeypatch.setattr(
        "src.predict.load_prediction_interval",
        lambda: {
            "residual_lower": 2.0,
            "residual_upper": 7.0,
        },
    )

    result = predict(
        _valid_payload()
    )

    assert result == {
        "eta_days": 10.0,
        "confidence_low": 12.0,
        "confidence_high": 17.0,
    }

    assert (
        result["confidence_low"]
        > result["eta_days"]
    )

    assert (
        result["confidence_low"]
        <= result["confidence_high"]
    )


def test_prediction_payload_validation():
    """Test required city-based prediction payload validation."""

    valid_payload = _valid_payload()

    _validate_payload(
        valid_payload
    )

    invalid_payload = valid_payload.copy()

    del invalid_payload["weight_kg"]

    with pytest.raises(
        ValueError,
        match="Missing required fields",
    ):
        _validate_payload(
            invalid_payload
        )


def test_negative_weight_is_rejected():
    """Negative shipment weight must be rejected."""

    payload = _valid_payload()

    payload["weight_kg"] = -1.0

    with pytest.raises(
        ValueError,
        match="weight_kg must be non-negative",
    ):
        _validate_payload(
            payload
        )


def test_invalid_origin_is_rejected():
    """Origin must be a non-empty city name."""

    payload = _valid_payload()

    payload["origin"] = {
        "lat": -23.5505,
        "lng": -46.6333,
    }

    with pytest.raises(
        ValueError,
        match="origin must be a city name",
    ):
        _validate_payload(
            payload
        )


def test_invalid_destination_is_rejected():
    """Destination must be a non-empty city name."""

    payload = _valid_payload()

    payload["destination"] = {
        "lat": -22.9068,
        "lng": -43.1729,
    }

    with pytest.raises(
        ValueError,
        match="destination must be a city name",
    ):
        _validate_payload(
            payload
        )


def test_empty_origin_city_is_rejected():
    """An empty origin city must be rejected."""

    payload = _valid_payload()

    payload["origin"] = "   "

    with pytest.raises(
        ValueError,
        match="origin city name must not be empty",
    ):
        _validate_payload(
            payload
        )


def test_empty_destination_city_is_rejected():
    """An empty destination city must be rejected."""

    payload = _valid_payload()

    payload["destination"] = ""

    with pytest.raises(
        ValueError,
        match="destination city name must not be empty",
    ):
        _validate_payload(
            payload
        )


def test_non_numeric_weight_is_rejected():
    """Non-numeric shipment weight must be rejected."""

    payload = _valid_payload()

    payload["weight_kg"] = "2.5"

    with pytest.raises(
        ValueError,
        match="weight_kg must be numeric",
    ):
        _validate_payload(
            payload
        )


def test_infinite_weight_is_rejected():
    """Infinite shipment weight must be rejected."""

    payload = _valid_payload()

    payload["weight_kg"] = float(
        "inf"
    )

    with pytest.raises(
        ValueError,
        match="weight_kg must be finite",
    ):
        _validate_payload(
            payload
        )


def test_unknown_origin_city_is_rejected(
    patch_city_coordinates,
):
    """Unknown origin city must be rejected."""

    payload = _valid_payload()

    payload["origin"] = (
        "city_that_does_not_exist"
    )

    with pytest.raises(
        ValueError,
        match="City not found in geolocation dataset",
    ):
        prepare_prediction_input(
            payload
        )


def test_unknown_destination_city_is_rejected(
    patch_city_coordinates,
):
    """Unknown destination city must be rejected."""

    payload = _valid_payload()

    payload["destination"] = (
        "city_that_does_not_exist"
    )

    with pytest.raises(
        ValueError,
        match="City not found in geolocation dataset",
    ):
        prepare_prediction_input(
            payload
        )


def test_city_lookup_is_case_and_whitespace_insensitive(
    patch_city_coordinates,
):
    """City lookup should normalize case and surrounding whitespace."""

    normal_coordinates = (
        _lookup_city_coordinates(
            "city_a"
        )
    )

    normalized_coordinates = (
        _lookup_city_coordinates(
            "  CITY_A  "
        )
    )

    assert np.allclose(
        normal_coordinates,
        normalized_coordinates,
    )


def test_city_coordinates_are_valid(
    patch_city_coordinates,
):
    """Resolved city coordinates must be geographically valid."""

    latitude, longitude = (
        _lookup_city_coordinates(
            "city_a"
        )
    )

    assert -90.0 <= latitude <= 90.0
    assert -180.0 <= longitude <= 180.0

    assert np.isfinite(
        latitude
    )

    assert np.isfinite(
        longitude
    )


def test_distance_calculation():
    """Verify distance calculation returns a valid distance."""

    distance = _calculate_distance(
        -23.5505,
        -46.6333,
        -22.9068,
        -43.1729,
    )

    assert distance > 0

    assert np.isfinite(
        distance
    )


def test_same_location_has_zero_distance():
    """Identical origin and destination must have zero distance."""

    distance = _calculate_distance(
        -23.5505,
        -46.6333,
        -23.5505,
        -46.6333,
    )

    assert np.isclose(
        distance,
        0.0,
    )


def test_invalid_latitude_is_rejected():
    """Latitude outside the valid geographic range must be rejected."""

    with pytest.raises(
        ValueError,
        match="origin_lat must be between",
    ):
        _calculate_distance(
            91.0,
            -46.6333,
            -22.9068,
            -43.1729,
        )


def test_invalid_longitude_is_rejected():
    """Longitude outside the valid geographic range must be rejected."""

    with pytest.raises(
        ValueError,
        match="origin_lng must be between",
    ):
        _calculate_distance(
            -23.5505,
            181.0,
            -22.9068,
            -43.1729,
        )


def test_nan_coordinate_is_rejected():
    """NaN coordinates must be rejected."""

    with pytest.raises(
        ValueError,
        match="origin_lat must be finite",
    ):
        _calculate_distance(
            float("nan"),
            -46.6333,
            -22.9068,
            -43.1729,
        )


def test_infinite_coordinate_is_rejected():
    """Infinite coordinates must be rejected."""

    with pytest.raises(
        ValueError,
        match="destination_lng must be finite",
    ):
        _calculate_distance(
            -23.5505,
            -46.6333,
            -22.9068,
            float("inf"),
        )