import pandas as pd
import pytest

from src.production_model import ProductionForecastModel


def test_load_requires_model_name(monkeypatch):
    monkeypatch.delenv("MLFLOW_MODEL_NAME", raising=False)
    model = ProductionForecastModel()

    with pytest.raises(RuntimeError, match="MLFLOW_MODEL_NAME"):
        model.load()


def test_load_fails_when_production_model_is_missing(monkeypatch):
    monkeypatch.setenv("MLFLOW_MODEL_NAME", "demand-forecast-test")
    monkeypatch.setenv("MLFLOW_MODEL_STAGE", "Production")

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def get_latest_versions(self, name, stages):
            return []

    monkeypatch.setattr("src.production_model.mlflow.set_tracking_uri", lambda uri: None)
    monkeypatch.setattr("src.production_model.MlflowClient", FakeClient)

    model = ProductionForecastModel()

    with pytest.raises(RuntimeError, match="No registered model version"):
        model.load()

    assert model.is_loaded is False


def test_predict_fails_when_model_is_not_loaded():
    model = ProductionForecastModel()

    with pytest.raises(RuntimeError, match="not loaded"):
        model.predict("SKU-000123", "WH-BLR-01", 1)


def test_predict_returns_contract_daily_points():
    model = ProductionForecastModel()
    model.model_version = "7"

    class FakePyfuncModel:
        def predict(self, frame):
            assert list(frame.columns) == [
                "sku_id",
                "warehouse_id",
                "horizon",
            ]
            assert frame.iloc[0]["sku_id"] == "SKU-000123"
            assert frame.iloc[0]["warehouse_id"] == "WH-BLR-01"
            assert frame.iloc[0]["horizon"] == 2

            return pd.DataFrame([
                {
                    "date": "2026-10-28",
                    "predicted": 10,
                    "lower_bound": 8,
                    "upper_bound": 12,
                },
                {
                    "date": "2026-10-29",
                    "predicted": 11,
                    "lower_bound": 9,
                    "upper_bound": 13,
                },
            ])

    model.model = FakePyfuncModel()

    result = model.predict("SKU-000123", "WH-BLR-01", 2)

    assert len(result) == 2
    assert result[0]["date"] == "2026-10-28"
    assert result[1]["date"] == "2026-10-29"
    assert result[0]["lower_bound"] <= result[0]["predicted"]
    assert result[0]["predicted"] <= result[0]["upper_bound"]


def test_predict_rejects_invalid_forecast_bounds():
    model = ProductionForecastModel()
    model.model_version = "7"

    class FakePyfuncModel:
        def predict(self, frame):
            return [{
                "date": "2026-10-28",
                "predicted": 10,
                "lower_bound": 12,
                "upper_bound": 14,
            }]

    model.model = FakePyfuncModel()

    with pytest.raises(ValueError, match="Forecast bounds"):
        model.predict("SKU-000123", "WH-BLR-01", 1)
