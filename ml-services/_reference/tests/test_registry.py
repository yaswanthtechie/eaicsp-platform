from src.registry import (
    get_model,
    list_models,
    model_exists,
    get_production_version,
)


def test_all_required_models_are_registered():

    models = list_models()

    names = {
        model["model_name"]
        for model in models
    }

    assert names == {
        "forecast",
        "eta",
        "anomaly",
        "risk",
    }


def test_model_exists():

    assert model_exists("forecast")
    assert model_exists("eta")
    assert model_exists("anomaly")
    assert model_exists("risk")


def test_unknown_model_does_not_exist():

    assert not model_exists("unknown")


def test_independent_versions():

    assert get_production_version(
        "forecast"
    ) == "v1"

    assert get_production_version(
        "eta"
    ) == "v1"

    assert get_production_version(
        "anomaly"
    ) == "v1"

    assert get_production_version(
        "risk"
    ) == "v1"