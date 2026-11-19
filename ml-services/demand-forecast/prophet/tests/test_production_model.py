import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from src.production_model import ProductionForecastModel


def configure_model(monkeypatch, tmp_path):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    monkeypatch.setenv("MLFLOW_MODEL_NAME", "demand_forecast")
    monkeypatch.setenv("MLFLOW_MODEL_ALIAS", "production")
    monkeypatch.setenv("MLFLOW_MODEL_CACHE_DIR", str(tmp_path))


def test_load_requires_model_name(monkeypatch, tmp_path):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    monkeypatch.delenv("MLFLOW_MODEL_NAME", raising=False)
    monkeypatch.setenv("MLFLOW_MODEL_CACHE_DIR", str(tmp_path))

    model = ProductionForecastModel()

    with pytest.raises(RuntimeError, match="MLFLOW_MODEL_NAME"):
        model.load()


def test_load_requires_tracking_uri(monkeypatch, tmp_path):
    monkeypatch.setenv("MLFLOW_MODEL_NAME", "demand_forecast")
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    monkeypatch.setenv("MLFLOW_MODEL_CACHE_DIR", str(tmp_path))

    model = ProductionForecastModel()

    with pytest.raises(RuntimeError, match="MLFLOW_TRACKING_URI"):
        model.load()


def test_load_fails_when_production_alias_is_missing(
    monkeypatch, tmp_path
):
    configure_model(monkeypatch, tmp_path)

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def get_model_version_by_alias(self, name, alias):
            assert name == "demand_forecast"
            assert alias == "production"
            raise RuntimeError("No registered model version for production alias")

    monkeypatch.setattr(
        "src.production_model.mlflow.set_tracking_uri",
        lambda uri: None,
    )
    monkeypatch.setattr("src.production_model.MlflowClient", FakeClient)

    model = ProductionForecastModel()

    with pytest.raises(RuntimeError, match="No registered model version"):
        model.load()

    assert model.is_loaded is False
    assert model.load_status == "unhealthy"


def test_load_uses_production_alias_and_reload_gets_new_version(
    monkeypatch, tmp_path
):
    configure_model(monkeypatch, tmp_path)

    versions = iter(["1", "2"])
    alias_calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def get_model_version_by_alias(self, name, alias):
            alias_calls.append((name, alias))
            return SimpleNamespace(version=next(versions))

    class FakePyfuncModel:
        def predict(self, frame):
            return []

    def fake_download_artifacts(artifact_uri, dst_path):
        from pathlib import Path

        artifact_dir = Path(dst_path)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "MLmodel").write_text("test model")
        return str(artifact_dir)

    loaded_uris = []

    def fake_load_model(uri):
        from pathlib import Path

        model_path = Path(uri)
        assert (model_path / "MLmodel").is_file()
        loaded_uris.append(str(model_path))
        return FakePyfuncModel()

    monkeypatch.setattr(
        "src.production_model.mlflow.set_tracking_uri",
        lambda uri: None,
    )
    monkeypatch.setattr("src.production_model.MlflowClient", FakeClient)
    monkeypatch.setattr(
        "src.production_model.mlflow.artifacts.download_artifacts",
        fake_download_artifacts,
    )
    monkeypatch.setattr(
        "src.production_model.mlflow.pyfunc.load_model",
        fake_load_model,
    )

    model = ProductionForecastModel()

    model.load()
    assert model.model_version == "1"
    assert model.load_status == "ready"

    model.load()
    assert model.model_version == "2"
    assert model.load_status == "ready"

    assert alias_calls == [
        ("demand_forecast", "production"),
        ("demand_forecast", "production"),
    ]
    assert [Path(uri).parent.name for uri in loaded_uris] == [
        "demand_forecast",
        "demand_forecast",
    ]
    assert [Path(uri).name for uri in loaded_uris] == ["1", "2"]


def test_load_uses_cached_model_when_mlflow_is_unavailable(
    monkeypatch, tmp_path
):
    configure_model(monkeypatch, tmp_path)

    cache_dir = tmp_path / "demand_forecast" / "7"
    cache_dir.mkdir(parents=True)
    (cache_dir / "MLmodel").write_text("cached model")

    metadata = {
        "model_name": "demand_forecast",
        "model_alias": "production",
        "model_version": "7",
        "model_path": "demand_forecast/7",
    }

    (tmp_path / "latest.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def get_model_version_by_alias(self, name, alias):
            raise ConnectionError("MLflow server unavailable")

    class FakePyfuncModel:
        pass

    monkeypatch.setattr(
        "src.production_model.mlflow.set_tracking_uri",
        lambda uri: None,
    )
    monkeypatch.setattr("src.production_model.MlflowClient", FakeClient)
    monkeypatch.setattr(
        "src.production_model.mlflow.pyfunc.load_model",
        lambda uri: FakePyfuncModel(),
    )

    model = ProductionForecastModel()
    model.load()

    assert model.is_loaded is True
    assert model.model_version == "7"
    assert model.load_status == "degraded"
    assert "MLflow server unavailable" in model.load_error


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
