"""Tests for the ETA model adapter."""

import pytest

from src.adapters.eta import ETAAdapter


def test_eta_adapter_metadata():
    adapter = ETAAdapter()

    metadata = adapter.metadata()

    assert metadata["model"] == "eta"
    assert metadata["model_version"] == "v1"
    assert metadata["status"] == "ready"


def test_eta_prediction():
    adapter = ETAAdapter()

    payload = {
        "origin": "sao paulo",
        "destination": "rio de janeiro",
        "carrier": "carrier-a",
        "weight_kg": 2.5,
    }

    result = adapter.predict(payload)

    assert result["eta_days"] == 5.0
    assert result["confidence_low"] == 4.0
    assert result["confidence_high"] == 6.0
    assert result["model_type"] == "stub"


def test_eta_rejects_missing_origin():
    adapter = ETAAdapter()

    with pytest.raises(ValueError):
        adapter.predict(
            {
                "destination": "rio de janeiro",
                "carrier": "carrier-a",
                "weight_kg": 2.5,
            }
        )


def test_eta_rejects_invalid_weight():
    adapter = ETAAdapter()

    with pytest.raises(ValueError):
        adapter.predict(
            {
                "origin": "sao paulo",
                "destination": "rio de janeiro",
                "carrier": "carrier-a",
                "weight_kg": 0,
            }
        )