from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.adapters.forecast import ForecastAdapter
from src.dashboard import create_dashboard_router
from src.model_manager import ModelManager
from src.monitoring import get_model_recent_inputs
from src.router import create_router


def test_plain_predictions_appear_on_the_dashboard_and_in_the_drift_window():
    """
    Real traffic through /models/{m}/predict must be visible to both
    Milestone 4 (dashboard) and Milestone 3 (drift input window).
    """
    manager = ModelManager()
    manager.register(ForecastAdapter())

    app = FastAPI()
    app.include_router(create_router(manager))
    app.include_router(create_dashboard_router(manager))

    client = TestClient(app)

    for _ in range(26):
        response = client.post(
            "/models/forecast/predict",
            json={"payload": {"history": [1, 2, 3]}},
        )

        assert response.status_code == 200

    # Milestone 4: dashboard must show real request traffic.
    html = client.get("/mlops/dashboard").text

    assert "Requests 0" not in html
    assert "26" in html

    # Milestone 3: drift monitoring must have recent inputs available.
    assert len(
        get_model_recent_inputs("forecast", limit=100)
    ) >= 26