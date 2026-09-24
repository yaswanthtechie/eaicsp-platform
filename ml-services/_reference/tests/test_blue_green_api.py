import pytest
from fastapi.testclient import TestClient

import src.service as svc
from src.governance import GovernanceManager


PAYLOAD = {"history": [100, 110, 120, 130], "horizon": 3}


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Isolated governance state; never touch the real governance file.
    governance = GovernanceManager(tmp_path / "governance.json")
    monkeypatch.setattr(svc.BLUE_GREEN_MANAGER, "governance", governance)

    yield TestClient(svc.multi_model_app, raise_server_exceptions=False), governance

    # Restore global serving state for other tests.
    svc.BLUE_GREEN_MANAGER.deployments.clear()
    svc.MULTI_MODEL_MANAGER.set_production_version("forecast", "v1")


def _served_versions(client):
    single = client.post("/models/forecast/predict", json={"payload": PAYLOAD})
    batch = client.post(
        "/models/batch-predict",
        json={"requests": [{"model_name": "forecast", "features": PAYLOAD}]},
    )
    listed = {m["model"]: m for m in client.get("/models").json()["models"]}

    return (
        single.json()["model_version"],
        batch.json()["results"][0]["prediction"]["model_version"],
        listed["forecast"]["production_version"],
    )


def test_blue_green_switch_controls_real_traffic(client):
    client, governance = client

    r = client.post(
        "/models/forecast/blue-green",
        json={"blue_version": "v1", "green_version": "v2"},
    )
    assert r.status_code == 200
    assert _served_versions(client) == ("v1", "v1", "v1")

    # Unapproved green is blocked, and traffic does not move.
    r = client.post("/models/forecast/blue-green/switch/green")
    assert r.status_code == 403
    assert _served_versions(client) == ("v1", "v1", "v1")

    governance.request_approval("forecast", "v2", requested_by="ajith", reason="candidate")
    governance.approve("forecast", "v2", approved_by="lead", reason="reviewed")

    # Approved: ALL production paths now serve v2.
    r = client.post("/models/forecast/blue-green/switch/green")
    assert r.status_code == 200
    assert _served_versions(client) == ("v2", "v2", "v2")

    # Rollback: back to v1 everywhere, no approval needed.
    r = client.post("/models/forecast/blue-green/switch/blue")
    assert r.status_code == 200
    assert _served_versions(client) == ("v1", "v1", "v1")


def test_configure_rejects_blue_that_is_not_live(client):
    client, _ = client

    r = client.post(
        "/models/forecast/blue-green",
        json={"blue_version": "v2", "green_version": "v1"},
    )
    assert r.status_code == 400
    assert "currently serving production" in r.json()["detail"]


def test_batch_over_limit_is_rejected(client):
    client, _ = client

    r = client.post(
        "/models/batch-predict",
        json={"requests": [{"model_name": "forecast", "features": PAYLOAD}] * 101},
    )
    assert r.status_code == 422