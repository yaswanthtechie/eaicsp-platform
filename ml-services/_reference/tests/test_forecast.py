"""Tests for the Forecast model adapter."""

import pytest

from src.adapters.forecast import ForecastAdapter


def test_forecast_adapter_metadata():
    adapter = ForecastAdapter()

    metadata = adapter.metadata()

    assert metadata["model"] == "forecast"
    assert metadata["model_version"] == "v1"
    assert metadata["status"] == "ready"


def test_forecast_prediction():
    adapter = ForecastAdapter()

    payload = {
        "history": [100, 110, 120, 130],
        "horizon": 3,
    }

    result = adapter.predict(payload)

    assert "forecast" in result
    assert result["forecast"] == [130.0, 130.0, 130.0]
    assert result["horizon"] == 3
    assert result["model_type"] == "stub"


def test_forecast_uses_last_value():
    adapter = ForecastAdapter()

    result = adapter.predict(
        {
            "history": [100, 150, 200],
            "horizon": 2,
        }
    )

    assert result["forecast"] == [200.0, 200.0]


def test_forecast_rejects_empty_history():
    adapter = ForecastAdapter()

    with pytest.raises(ValueError):
        adapter.predict(
            {
                "history": [],
                "horizon": 3,
            }
        )


def test_forecast_rejects_invalid_horizon():
    adapter = ForecastAdapter()

    with pytest.raises(ValueError):
        adapter.predict(
            {
                "history": [100, 110],
                "horizon": 0,
            }
        )