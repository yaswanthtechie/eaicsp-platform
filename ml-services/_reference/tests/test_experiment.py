import pytest

from src.experiment import ABExperiment


def test_experiment_creation():
    experiment = ABExperiment(
        model_name="forecast",
        variant_a="v1",
        variant_b="v2",
        traffic_percentage=50,
    )

    assert experiment.model_name == "forecast"
    assert experiment.variant_a == "v1"
    assert experiment.variant_b == "v2"
    assert experiment.traffic_percentage == 50


def test_experiment_rejects_same_variants():
    with pytest.raises(ValueError):
        ABExperiment(
            model_name="forecast",
            variant_a="v1",
            variant_b="v1",
        )


def test_experiment_rejects_invalid_percentage():
    with pytest.raises(ValueError):
        ABExperiment(
            model_name="forecast",
            variant_a="v1",
            variant_b="v2",
            traffic_percentage=101,
        )


def test_experiment_rejects_negative_percentage():
    with pytest.raises(ValueError):
        ABExperiment(
            model_name="forecast",
            variant_a="v1",
            variant_b="v2",
            traffic_percentage=-1,
        )