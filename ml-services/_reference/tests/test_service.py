import pytest

from src.service import IrisService, IrisRequest


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


def test_invalid_input():
    with pytest.raises(Exception):
        IrisRequest(
            features=[5.1, 3.5]
        )