from unittest.mock import Mock

import pytest

from src.blue_green import BlueGreenManager


class FakeAdapter:
    def __init__(
        self,
        model_name,
        model_version,
    ):
        self.model_name = model_name
        self.model_version = model_version

    def predict(self, payload):
        return {
            "prediction": f"{self.model_version}-prediction"
        }


def create_manager():
    model_manager = Mock()

    adapters = {
        "v1": FakeAdapter(
            "forecast",
            "v1",
        ),
        "v2": FakeAdapter(
            "forecast",
            "v2",
        ),
    }

    def get_version_adapter(
        model_name,
        version,
    ):
        if version not in adapters:
            raise KeyError(
                f"Version '{version}' not found"
            )

        return adapters[version]

    def predict_version(
        model_name,
        version,
        payload,
        variant=None,
        quality_score=None,
    ):
        adapter = adapters[version]

        return {
            "model": adapter.model_name,
            "model_version": adapter.model_version,
            "prediction": (
                f"{version}-prediction"
            ),
            "confidence": None,
            "quality_score": quality_score,
            "latency_ms": 1.0,
        }

    model_manager.get_version_adapter.side_effect = (
        get_version_adapter
    )

    model_manager.predict_version.side_effect = (
        predict_version
    )

    return model_manager


def test_configure_blue_green():
    manager = BlueGreenManager(
        create_manager()
    )

    result = manager.configure(
        model_name="forecast",
        blue_version="v1",
        green_version="v2",
    )

    assert result["model_name"] == "forecast"
    assert result["blue_version"] == "v1"
    assert result["green_version"] == "v2"
    assert result["active_color"] == "blue"
    assert result["active_version"] == "v1"


def test_blue_is_active_initially():
    manager = BlueGreenManager(
        create_manager()
    )

    manager.configure(
        "forecast",
        "v1",
        "v2",
    )

    result = manager.predict(
        "forecast",
        {"history": [100, 110]},
    )

    assert result["model_version"] == "v1"
    assert result["deployment_color"] == "blue"


def test_switch_to_green():
    manager = BlueGreenManager(
        create_manager()
    )

    manager.configure(
        "forecast",
        "v1",
        "v2",
    )

    result = manager.switch_to_green(
        "forecast"
    )

    assert result["active_color"] == "green"
    assert result["active_version"] == "v2"


def test_green_receives_predictions_after_switch():
    manager = BlueGreenManager(
        create_manager()
    )

    manager.configure(
        "forecast",
        "v1",
        "v2",
    )

    manager.switch_to_green(
        "forecast"
    )

    result = manager.predict(
        "forecast",
        {"history": [100, 110]},
    )

    assert result["model_version"] == "v2"
    assert result["deployment_color"] == "green"


def test_switch_back_to_blue():
    manager = BlueGreenManager(
        create_manager()
    )

    manager.configure(
        "forecast",
        "v1",
        "v2",
    )

    manager.switch_to_green(
        "forecast"
    )

    result = manager.switch_to_blue(
        "forecast"
    )

    assert result["active_color"] == "blue"
    assert result["active_version"] == "v1"


def test_same_versions_are_rejected():
    manager = BlueGreenManager(
        create_manager()
    )

    with pytest.raises(
        ValueError,
        match="must be different",
    ):
        manager.configure(
            "forecast",
            "v1",
            "v1",
        )


def test_missing_version_is_rejected():
    manager = BlueGreenManager(
        create_manager()
    )

    with pytest.raises(KeyError):
        manager.configure(
            "forecast",
            "v1",
            "v3",
        )