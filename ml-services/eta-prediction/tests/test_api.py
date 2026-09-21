
import pytest
from fastapi.testclient import TestClient

from src.api import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_predict_success(client, monkeypatch):
    def fake_predict(payload):
        return {
            "eta_days": 10.5,
            "confidence_low": 5.0,
            "confidence_high": 16.0,
        }

    monkeypatch.setattr("src.api.predict", fake_predict)

    response = client.post(
        "/predict",
        json={
            "origin": "sao paulo",
            "destination": "rio de janeiro",
            "carrier": "carrier_x",
            "weight_kg": 2.5,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["eta_days"] == 10.5
    assert body["confidence_low"] == 5.0
    assert body["confidence_high"] == 16.0


def test_predict_unknown_city_returns_structured_error(client, monkeypatch):
    def fake_predict(payload):
        raise ValueError(
            "City not found in geolocation dataset: unknown_city_xyz"
        )

    monkeypatch.setattr("src.api.predict", fake_predict)

    response = client.post(
        "/predict",
        json={
            "origin": "unknown_city_xyz",
            "destination": "rio de janeiro",
            "carrier": "carrier_x",
            "weight_kg": 2.5,
        },
    )

    assert response.status_code == 422

    body = response.json()

    assert body["detail"]["error_code"] == "LOCATION_NOT_FOUND"
    assert (
        body["detail"]["message"]
        == "City not found in geolocation dataset: unknown_city_xyz"
    )


def test_predict_invalid_request(client, monkeypatch):
    def fake_predict(payload):
        raise ValueError("Invalid prediction request")

    monkeypatch.setattr("src.api.predict", fake_predict)

    response = client.post(
        "/predict",
        json={
            "origin": "sao paulo",
            "destination": "rio de janeiro",
            "carrier": "carrier_x",
            "weight_kg": 2.5,
        },
    )

    assert response.status_code == 422

    body = response.json()

    assert body["detail"]["error_code"] == "INVALID_REQUEST"
    assert body["detail"]["message"] == "Invalid prediction request"


def test_predict_missing_required_field(client):
    response = client.post(
        "/predict",
        json={
            "origin": "sao paulo",
            "destination": "rio de janeiro",
            "carrier": "carrier_x",
        },
    )

    assert response.status_code == 422


def test_predict_negative_weight(client):
    response = client.post(
        "/predict",
        json={
            "origin": "sao paulo",
            "destination": "rio de janeiro",
            "carrier": "carrier_x",
            "weight_kg": -2.5,
        },
    )

    assert response.status_code == 422


def test_predict_unseen_carrier(client, monkeypatch):
    def fake_predict(payload):
        return {
            "eta_days": 20.0,
            "confidence_low": 10.0,
            "confidence_high": 30.0,
        }

    monkeypatch.setattr("src.api.predict", fake_predict)

    response = client.post(
        "/predict",
        json={
            "origin": "sao paulo",
            "destination": "rio de janeiro",
            "carrier": "completely_new_carrier_xyz",
            "weight_kg": 2.5,
        },
    )

    assert response.status_code == 200
    assert response.json()["eta_days"] == 20.0


def test_predict_internal_error(client, monkeypatch):
    def fake_predict(payload):
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr("src.api.predict", fake_predict)

    response = client.post(
        "/predict",
        json={
            "origin": "sao paulo",
            "destination": "rio de janeiro",
            "carrier": "carrier_x",
            "weight_kg": 2.5,
        },
    )

    assert response.status_code == 500

    body = response.json()

    assert body["detail"]["error_code"] == "INTERNAL_PREDICTION_ERROR"

