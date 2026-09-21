from fastapi.testclient import TestClient

from src.dashboard import create_dashboard_router
from src.model_manager import ModelManager
from src.adapters.forecast import ForecastAdapter
from src.adapters.eta import ETAAdapter
from src.adapters.anomaly import AnomalyAdapter
from src.adapters.risk import RiskAdapter


def build_manager() -> ModelManager:
    manager = ModelManager()

    manager.register(ForecastAdapter())
    manager.register(ETAAdapter())
    manager.register(AnomalyAdapter())
    manager.register(RiskAdapter())

    return manager


def build_app():
    from fastapi import FastAPI

    manager = build_manager()

    app = FastAPI()

    app.include_router(
        create_dashboard_router(
            model_manager=manager,
        )
    )

    return app


def test_dashboard_endpoint_returns_html():
    app = build_app()
    client = TestClient(app)

    response = client.get("/mlops/dashboard")

    assert response.status_code == 200
    assert "MLOps Dashboard" in response.text


def test_dashboard_contains_all_models():
    app = build_app()
    client = TestClient(app)

    response = client.get("/mlops/dashboard")

    assert response.status_code == 200

    assert "Forecast" in response.text
    assert "Eta" in response.text
    assert "Anomaly" in response.text
    assert "Risk" in response.text


def test_dashboard_contains_model_metrics():
    app = build_app()
    client = TestClient(app)

    response = client.get("/mlops/dashboard")

    assert response.status_code == 200

    assert "Production Version" in response.text
    assert "Requests" in response.text
    assert "Avg Latency" in response.text
    assert "A/B Metrics" in response.text


def test_dashboard_is_read_only():
    app = build_app()
    client = TestClient(app)

    response = client.get("/mlops/dashboard")

    assert response.status_code == 200

    assert "POST" not in response.text
    assert "DELETE" not in response.text