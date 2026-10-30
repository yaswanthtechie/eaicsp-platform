"""Endpoint tests for the A2 forecast contract (no MLflow or Platform needed)."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import src.bentoml_service as svc

URL = "/api/v1/demand/forecast/SKU-000123"
OK_PARAMS = {"warehouse_id": "WH-BLR-01", "horizon": 2}
KEY = {"X-API-Key": "test-key"}

POINTS = [
    {
        "date": "2026-10-30",
        "predicted": 10.0,
        "lower_bound": 8.0,
        "upper_bound": 12.0,
    },
    {
        "date": "2026-10-31",
        "predicted": 11.0,
        "lower_bound": 9.0,
        "upper_bound": 13.0,
    },
]


class FakeModel:
    def __init__(self, loaded: bool):
        self.is_loaded = loaded
        self.model_version = "7" if loaded else None

    def predict(self, sku_id, warehouse_id, horizon):
        return POINTS[:horizon]


def make_client(monkeypatch, loaded=True, auth_ok=True):
    svc.app.state.forecast_service = SimpleNamespace(
        production_model=FakeModel(loaded),
        total_predictions=0,
        total_latency=0.0,
        error_count=0,
        load_error=None if loaded else "No registered model version",
        try_load=lambda force=False: None,
    )

    if auth_ok:
        monkeypatch.setattr(svc, "verify_platform_api_key", lambda key: None)

    return TestClient(svc.app)


def test_health_is_503_until_model_loaded(monkeypatch):
    response = make_client(monkeypatch, loaded=False).get("/health")
    assert response.status_code == 503


def test_health_is_200_when_model_loaded(monkeypatch):
    response = make_client(monkeypatch).get("/health")
    assert response.status_code == 200
    assert response.json()["model_loaded"] is True


def test_valid_request_matches_contract(monkeypatch):
    response = make_client(monkeypatch).get(
        URL, params=OK_PARAMS, headers=KEY
    )

    assert response.status_code == 200
    body = response.json()

    assert set(body) == {
        "contract_version",
        "sku_id",
        "warehouse_id",
        "granularity",
        "horizon",
        "interval_level",
        "model_version",
        "generated_at",
        "forecast",
    }
    assert body["contract_version"] == "v1"
    assert body["granularity"] == "daily"
    assert body["interval_level"] == 0.8
    assert body["sku_id"] == "SKU-000123"
    assert body["warehouse_id"] == "WH-BLR-01"
    assert body["horizon"] == 2
    assert len(body["forecast"]) == 2
    assert set(body["forecast"][0]) == {
        "date",
        "predicted",
        "lower_bound",
        "upper_bound",
    }


def test_missing_api_key_returns_401_contract_error(monkeypatch):
    response = make_client(monkeypatch, auth_ok=False).get(
        URL, params=OK_PARAMS
    )

    assert response.status_code == 401
    assert response.json() == {
        "error_code": "UNAUTHORIZED",
        "message": "Missing service API key",
    }


@pytest.mark.parametrize(
    "url,params",
    [
        ("/api/v1/demand/forecast/SKU-123", OK_PARAMS),
        (URL, {"warehouse_id": "WH-MUM-1", "horizon": 2}),
        (URL, {"warehouse_id": "WH-BLR-01", "horizon": 0}),
        (URL, {"warehouse_id": "WH-BLR-01", "horizon": 91}),
        (URL, {"horizon": 2}),
    ],
)
def test_bad_parameters_return_400_invalid_parameter(
    monkeypatch, url, params
):
    response = make_client(monkeypatch).get(
        url, params=params, headers=KEY
    )

    assert response.status_code == 400
    assert set(response.json()) == {"error_code", "message"}
    assert response.json()["error_code"] == "INVALID_PARAMETER"


def test_model_not_loaded_returns_503_model_unavailable(monkeypatch):
    response = make_client(monkeypatch, loaded=False).get(
        URL, params=OK_PARAMS, headers=KEY
    )

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "MODEL_UNAVAILABLE",
        "message": "Forecast model is not loaded",
    }
