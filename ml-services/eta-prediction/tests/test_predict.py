import numpy as np
import pytest

from src.model_loader import (
    _calculate_distance,
    _validate_payload,
    load_model,
)
from src.predict import (
    predict,
    prepare_prediction_input,
)


def _valid_payload():
    """Return a valid logistics-service prediction payload."""

    return {
        "origin": {
            "lat": -23.5505,
            "lng": -46.6333,
        },
        "destination": {
            "lat": -22.9068,
            "lng": -43.1729,
        },
        "carrier": "proxy-carrier",
        "weight_kg": 2.5,
    }


def test_model_loader_and_prediction_lifecycle(
    trained_model_path,
):
    """
    Test the complete model-loader and prediction lifecycle.

    The trained_model_path fixture creates a temporary trained
    pipeline, so this test works on a fresh clone.
    """

    # ---------------------------------------------------------
    # 1. Temporary trained model must exist
    # ---------------------------------------------------------
    assert trained_model_path.exists()

    # ---------------------------------------------------------
    # 2. Load the trained model through model_loader
    # ---------------------------------------------------------
    model = load_model()

    assert model is not None
    assert hasattr(model, "predict")

    # ---------------------------------------------------------
    # 3. Logistics-service payload
    # ---------------------------------------------------------
    payload = _valid_payload()

    # ---------------------------------------------------------
    # 4. Convert service payload into model input
    # ---------------------------------------------------------
    features = prepare_prediction_input(
        payload
    )

    # ---------------------------------------------------------
    # 5. Verify model-compatible input
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # 6. Carrier is accepted as a service-level proxy,
    #    but is NOT a model feature.
    # ---------------------------------------------------------
    assert "carrier" not in features.columns

    # ---------------------------------------------------------
    # 7. Verify input mapping
    # ---------------------------------------------------------
    row = features.iloc[0]

    assert (
        row["origin_lat"]
        == payload["origin"]["lat"]
    )

    assert (
        row["origin_lng"]
        == payload["origin"]["lng"]
    )

    assert (
        row["destination_lat"]
        == payload["destination"]["lat"]
    )

    assert (
        row["destination_lng"]
        == payload["destination"]["lng"]
    )

    assert (
        row["total_weight_kg"]
        == payload["weight_kg"]
    )

    assert (
        row["product_category_name"]
        == "unknown"
    )

    # ---------------------------------------------------------
    # 8. Distance must be calculated
    # ---------------------------------------------------------
    assert row["distance_km"] > 0

    assert np.isfinite(
        row["distance_km"]
    )

    # ---------------------------------------------------------
    # 9. Loaded trained model must accept the
    #    prepared prediction input.
    # ---------------------------------------------------------
    prediction = model.predict(
        features
    )

    # ---------------------------------------------------------
    # 10. Verify raw model prediction
    # ---------------------------------------------------------
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
):
    """
    Verify the public predict() function follows the exact
    logistics-service contract required by Round 4.

    The prediction must contain:
        eta_days
        confidence_low
        confidence_high
    """

    # ---------------------------------------------------------
    # 1. Temporary trained model must exist
    # ---------------------------------------------------------
    assert trained_model_path.exists()

    # ---------------------------------------------------------
    # 2. Logistics-service payload
    # ---------------------------------------------------------
    payload = _valid_payload()

    # ---------------------------------------------------------
    # 3. Call the public prediction contract
    # ---------------------------------------------------------
    result = predict(
        payload
    )

    # ---------------------------------------------------------
    # 4. Exact output shape
    # ---------------------------------------------------------
    assert set(result.keys()) == {
        "eta_days",
        "confidence_low",
        "confidence_high",
    }

    # ---------------------------------------------------------
    # 5. ETA must be a valid numeric value
    # ---------------------------------------------------------
    assert isinstance(
        result["eta_days"],
        float,
    )

    assert np.isfinite(
        result["eta_days"]
    )

    assert result["eta_days"] >= 0

    # ---------------------------------------------------------
    # 6. Confidence interval must be available
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # 7. Confidence interval must be logically ordered
    # ---------------------------------------------------------
    assert (
        result["confidence_low"]
        <= result["eta_days"]
    )

    assert (
        result["eta_days"]
        <= result["confidence_high"]
    )

    assert (
        result["confidence_low"]
        <= result["confidence_high"]
    )

    # ---------------------------------------------------------
    # 8. Confidence interval must not be negative
    # ---------------------------------------------------------
    assert (
        result["confidence_low"]
        >= 0
    )

    assert (
        result["confidence_high"]
        >= 0
    )


def test_prediction_payload_validation():
    """Test required prediction payload validation."""

    valid_payload = _valid_payload()

    # Valid payload must pass.
    _validate_payload(
        valid_payload
    )

    # ---------------------------------------------------------
    # Missing required field
    # ---------------------------------------------------------
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
    """Origin without latitude must be rejected."""

    payload = _valid_payload()

    del payload["origin"]["lat"]

    with pytest.raises(
        ValueError,
        match="origin must contain lat",
    ):
        _validate_payload(
            payload
        )


def test_invalid_destination_is_rejected():
    """Destination without longitude must be rejected."""

    payload = _valid_payload()

    del payload["destination"]["lng"]

    with pytest.raises(
        ValueError,
        match="destination must contain lng",
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