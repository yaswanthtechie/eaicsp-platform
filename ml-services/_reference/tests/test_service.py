import pytest

from src.service import (
    IrisService,
    IrisRequest,
    IrisBatchRequest,
)


@pytest.fixture
def service():
    return IrisService()


def test_valid_prediction(service):
    request = IrisRequest(
        features=[5.1, 3.5, 1.4, 0.2]
    )

    response = service.predict(request)

    assert response.prediction in [
        "setosa",
        "versicolor",
        "virginica",
    ]

    assert 0.0 <= response.confidence <= 1.0
    assert response.model_version is not None
    assert len(response.probabilities) == 3
    assert response.latency_ms >= 0


def test_invalid_input():
    with pytest.raises(Exception):
        IrisRequest(
            features=[5.1, 3.5]
        )


def test_health(service):
    response = service.health()

    assert response["status"] == "healthy"
    assert "model_version" in response
    assert "canary_prediction" in response


def test_metrics(service):

    request = IrisRequest(
        features=[5.1, 3.5, 1.4, 0.2]
    )

    service.predict(request)

    metrics = service.service_metrics()

    assert metrics["total_predictions"] >= 1
    assert metrics["average_latency_ms"] >= 0
    assert metrics["error_count"] >= 0


def test_batch_prediction(service):

    request = IrisBatchRequest(
        features=[
            [5.1, 3.5, 1.4, 0.2],
            [6.7, 3.1, 4.7, 1.5],
            [7.2, 3.6, 6.1, 2.5],
        ]
    )

    response = service.predict_batch(request)

    assert len(response["predictions"]) == 3
    assert response["batch_latency_ms"] >= 0

    for prediction in response["predictions"]:
        assert prediction["prediction"] in [
            "setosa",
            "versicolor",
            "virginica",
        ]
        assert prediction["confidence"] >= 0
        assert prediction["latency_ms"] >= 0
        assert prediction["model_version"] is not None