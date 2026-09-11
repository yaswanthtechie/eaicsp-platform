"""Tests for unified multi-model serving."""

import pytest

from src.adapters.anomaly import AnomalyAdapter
from src.adapters.eta import ETAAdapter
from src.adapters.forecast import ForecastAdapter
from src.adapters.risk import RiskAdapter
from src.model_manager import ModelManager


def create_manager() -> ModelManager:
    manager = ModelManager()

    manager.register(ForecastAdapter())
    manager.register(ETAAdapter())
    manager.register(AnomalyAdapter())
    manager.register(RiskAdapter())

    return manager


def test_all_models_are_registered():
    manager = create_manager()

    models = manager.list_models()

    model_names = {model["model"] for model in models}

    assert model_names == {
        "forecast",
        "eta",
        "anomaly",
        "risk",
    }


def test_forecast_prediction_through_manager():
    manager = create_manager()

    result = manager.predict(
        "forecast",
        {
            "history": [100, 110, 120],
            "horizon": 2,
        },
    )

    assert result["model"] == "forecast"
    assert result["model_version"] == "v1"

    assert result["prediction"]["forecast"] == [120.0, 120.0]
    assert result["prediction"]["horizon"] == 2
    assert result["prediction"]["model_type"] == "stub"

    assert result["latency_ms"] >= 0


def test_eta_prediction_through_manager():
    manager = create_manager()

    result = manager.predict(
        "eta",
        {
            "origin": "sao paulo",
            "destination": "rio de janeiro",
            "carrier": "carrier-a",
            "weight_kg": 2.5,
        },
    )

    assert result["model"] == "eta"
    assert result["model_version"] == "v1"

    assert result["prediction"]["eta_days"] == 5.0
    assert result["prediction"]["confidence_low"] == 4.0
    assert result["prediction"]["confidence_high"] == 6.0

    assert result["latency_ms"] >= 0


def test_anomaly_prediction_through_manager():
    manager = create_manager()

    result = manager.predict(
        "anomaly",
        {
            "temperature": 90,
            "humidity": 50,
            "stock_count": 100,
        },
    )

    assert result["model"] == "anomaly"
    assert result["model_version"] == "v1"

    assert result["prediction"]["is_anomaly"] is True
    assert result["prediction"]["score"] == 0.85
    assert result["prediction"]["label"] == "anomaly"


def test_risk_prediction_through_manager():
    manager = create_manager()

    result = manager.predict(
        "risk",
        {
            "supplier_name": "Supplier A",
            "headlines": [
                "Supplier expands operations",
            ],
        },
    )

    assert result["model"] == "risk"
    assert result["model_version"] == "v1"

    assert result["prediction"]["risk_score"] == 0.25
    assert result["prediction"]["confidence"] == 0.75
    assert result["prediction"]["risk_level"] == "low"


def test_unknown_model_is_rejected():
    manager = create_manager()

    with pytest.raises(KeyError):
        manager.predict("unknown", {})


def test_health_reports_all_models():
    manager = create_manager()

    health = manager.health()

    assert health["status"] == "healthy"

    assert set(health["models"].keys()) == {
        "forecast",
        "eta",
        "anomaly",
        "risk",
    }

    for model in health["models"].values():
        assert model["status"] == "ready"
        assert model["version"] == "v1"