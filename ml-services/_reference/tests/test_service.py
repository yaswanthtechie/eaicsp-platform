import pytest
from pydantic import ValidationError

from src.service import (
    IrisService,
    IrisRequest,
    IrisBatchRequest,
)


@pytest.fixture
def service():
    return IrisService()


# ==========================================================
# Single Prediction Tests
# ==========================================================

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
    """
    Input must contain exactly four features.
    """

    with pytest.raises(ValidationError):
        IrisRequest(
            features=[5.1, 3.5]
        )


def test_malformed_prediction_input():
    """
    Malformed prediction input should be rejected.
    """

    with pytest.raises(ValidationError):
        IrisRequest(
            features=[5.1, 3.5, 1.4]
        )


def test_missing_prediction_input():
    """
    Missing features field should be rejected.
    """

    with pytest.raises(ValidationError):
        IrisRequest()


def test_invalid_feature_type():
    """
    Feature values must be numeric.
    """

    with pytest.raises(ValidationError):
        IrisRequest(
            features=[
                "abc",
                "xyz",
                "test",
                "value",
            ]
        )


# ==========================================================
# Health Test
# ==========================================================

def test_health(service):
    response = service.health()

    assert response["status"] == "healthy"
    assert "model_version" in response
    assert "canary_prediction" in response


# ==========================================================
# Metrics Test
# ==========================================================

def test_metrics(service):

    request = IrisRequest(
        features=[5.1, 3.5, 1.4, 0.2]
    )

    service.predict(request)

    metrics = service.metrics()

    assert metrics["total_predictions"] >= 1
    assert metrics["total_batches"] >= 0
    assert metrics["average_prediction_latency_ms"] >= 0
    assert metrics["average_batch_latency_ms"] >= 0
    assert metrics["error_count"] >= 0
    assert metrics["model_version"] is not None


# ==========================================================
# Batch Prediction Tests
# ==========================================================

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


def test_batch_missing_input():
    """
    Batch request must contain the features field.
    """

    with pytest.raises(ValidationError):
        IrisBatchRequest()


def test_batch_invalid_feature_count():
    """
    Every batch sample must contain exactly four features.
    """

    with pytest.raises(ValidationError):
        IrisBatchRequest(
            features=[
                [5.1, 3.5, 1.4],
                [6.7, 3.1, 4.7, 1.5],
            ]
        )


def test_empty_batch_input():
    """
    Batch request must contain at least one sample.
    """

    with pytest.raises(ValidationError):
        IrisBatchRequest(
            features=[]
        )


def test_batch_invalid_feature_type():
    """
    Batch features must be numeric.
    """

    with pytest.raises(ValidationError):
        IrisBatchRequest(
            features=[
                ["abc", "xyz", "test", "value"]
            ]
        )