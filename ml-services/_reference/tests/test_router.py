"""Tests for the unified multi-model FastAPI router."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.adapters.anomaly import AnomalyAdapter
from src.adapters.eta import ETAAdapter
from src.adapters.forecast import ForecastAdapter
from src.adapters.risk import RiskAdapter
from src.model_manager import ModelManager
from src.router import create_router


def create_test_client() -> TestClient:
    manager = ModelManager()

    manager.register(ForecastAdapter())
    manager.register(ETAAdapter())
    manager.register(AnomalyAdapter())
    manager.register(RiskAdapter())

    app = FastAPI()
    app.include_router(create_router(manager))

    return TestClient(app)


def test_list_models():
    client = create_test_client()

    response = client.get("/models")

    assert response.status_code == 200

    data = response.json()

    assert "models" in data

    model_names = {
        model["model"]
        for model in data["models"]
    }

    assert model_names == {
        "forecast",
        "eta",
        "anomaly",
        "risk",
    }


def test_get_forecast_model():
    client = create_test_client()

    response = client.get("/models/forecast")

    assert response.status_code == 200

    data = response.json()

    assert data["model"] == "forecast"
    assert data["production_version"] == "v1"
    assert data["status"] == "ready"


def test_forecast_prediction_endpoint():
    client = create_test_client()

    response = client.post(
        "/models/forecast/predict",
        json={
            "payload": {
                "history": [100, 110, 120],
                "horizon": 2,
            }
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["model"] == "forecast"
    assert data["model_version"] == "v1"

    assert data["prediction"]["forecast"] == [120.0, 120.0]
    assert data["prediction"]["horizon"] == 2
    assert data["prediction"]["model_type"] == "stub"

    assert data["latency_ms"] >= 0


def test_eta_prediction_endpoint():
    client = create_test_client()

    response = client.post(
        "/models/eta/predict",
        json={
            "payload": {
                "origin": "sao paulo",
                "destination": "rio de janeiro",
                "carrier": "carrier-a",
                "weight_kg": 2.5,
            }
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["model"] == "eta"
    assert data["model_version"] == "v1"

    assert data["prediction"]["eta_days"] == 5.0
    assert data["prediction"]["confidence_low"] == 4.0
    assert data["prediction"]["confidence_high"] == 6.0


def test_anomaly_prediction_endpoint():
    client = create_test_client()

    response = client.post(
        "/models/anomaly/predict",
        json={
            "payload": {
                "temperature": 90,
                "humidity": 50,
                "stock_count": 100,
            }
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["model"] == "anomaly"
    assert data["model_version"] == "v1"

    assert data["prediction"]["is_anomaly"] is True
    assert data["prediction"]["score"] == 0.85
    assert data["prediction"]["label"] == "anomaly"


def test_risk_prediction_endpoint():
    client = create_test_client()

    response = client.post(
        "/models/risk/predict",
        json={
            "payload": {
                "supplier_name": "Supplier A",
                "headlines": [
                    "Supplier expands operations",
                ],
            }
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["model"] == "risk"
    assert data["model_version"] == "v1"

    assert data["prediction"]["risk_score"] == 0.25
    assert data["prediction"]["confidence"] == 0.75
    assert data["prediction"]["risk_level"] == "low"


def test_unknown_model_returns_404():
    client = create_test_client()

    response = client.get("/models/unknown")

    assert response.status_code == 404


def test_unknown_model_prediction_returns_404():
    client = create_test_client()

    response = client.post(
        "/models/unknown/predict",
        json={
            "payload": {},
        },
    )

    assert response.status_code == 404


def test_invalid_forecast_input_returns_422():
    client = create_test_client()

    response = client.post(
        "/models/forecast/predict",
        json={
            "payload": {
                "history": [],
                "horizon": 3,
            }
        },
    )

    assert response.status_code == 422