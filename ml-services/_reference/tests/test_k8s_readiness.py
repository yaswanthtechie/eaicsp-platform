from unittest.mock import MagicMock, patch

from src.service import IrisService


def _make_service():
    with patch(
        "src.service.load_model",
        return_value=(MagicMock(), "7"),
    ), patch(
        "src.service.load_canary_models",
        return_value={
            "production": (MagicMock(), "7"),
            "staging": (MagicMock(), "8"),
        },
    ):
        return IrisService()


def test_ready_when_model_loaded_and_can_predict():
    service = _make_service()

    assert service.__is_ready__() is True
    service.model.predict.assert_called()


def test_not_ready_when_model_missing():
    service = _make_service()
    service.model = None

    assert service.__is_ready__() is False


def test_not_ready_when_model_cannot_predict():
    service = _make_service()
    service.model.predict.side_effect = RuntimeError("corrupt model")

    assert service.__is_ready__() is False


def test_no_custom_probe_routes_shadowing_bentoml():
    routes = {
        "/" + api.route.lstrip("/")
        for api in IrisService.apis.values()
    }

    assert "/readyz" not in routes
    assert "/livez" not in routes


def test_build_version_comes_from_env(monkeypatch):
    monkeypatch.setenv("MODEL_BUILD_VERSION", "v2")
    service = _make_service()

    assert service.model_info()["build_version"] == "v2"


def test_build_version_does_not_override_model_version(monkeypatch):
    monkeypatch.setenv("MODEL_BUILD_VERSION", "v2")
    service = _make_service()

    assert service.model_info()["model_version"] == "7"
    