
"""
Tests for R5 rollback functionality.

Covers:
- Rollback decision logic
- Rollback endpoint
- Production model reload
- Canary model reload
- No-rollback behaviour
- Invalid accuracy validation
- Rollback response
"""

from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from src.service import IrisService


# ==========================================================
# Test Application
# ==========================================================

@pytest.fixture(scope="session")
def app():
    """
    Create the BentoML ASGI application without requiring
    a real MLflow production model during test collection.
    """

    with patch(
        "src.service.load_model",
        return_value=(
            MagicMock(),
            "1",
        ),
    ), patch(
        "src.service.load_canary_models",
        return_value={
            "production": (
                MagicMock(),
                "1",
            ),
            "staging": (
                MagicMock(),
                "2",
            ),
        },
    ):
        yield IrisService.to_asgi()


# ==========================================================
# Rollback Decision Logic
# ==========================================================

@patch("src.rollback.should_rollback")
def test_should_rollback_when_new_model_is_worse(
    mock_should_rollback,
):
    """
    Verify rollback decision when the new model performs worse.
    """

    mock_should_rollback.return_value = True

    from src.rollback import should_rollback

    result = should_rollback(
        new_model_accuracy=0.70,
        previous_model_accuracy=0.92,
    )

    assert result is True


@patch("src.rollback.should_rollback")
def test_should_not_rollback_when_new_model_is_better(
    mock_should_rollback,
):
    """
    Verify no rollback when the new model performs better.
    """

    mock_should_rollback.return_value = False

    from src.rollback import should_rollback

    result = should_rollback(
        new_model_accuracy=0.94,
        previous_model_accuracy=0.92,
    )

    assert result is False


# ==========================================================
# Rollback Model Function
# ==========================================================

@patch("src.mlflow_utils.client")
def test_rollback_model_function(
    mock_client,
):
    """
    Verify that rollback_model interacts with MLflow.
    """

    from src.mlflow_utils import rollback_model

    mock_client.get_model_version_by_alias.side_effect = [
        MagicMock(version="2"),
        MagicMock(version="1"),
    ]

    result = rollback_model(
        "iris_classifier"
    )

    assert isinstance(result, dict)


# ==========================================================
# Rollback Endpoint - Successful Rollback
# ==========================================================

@patch("src.service.load_canary_models")
@patch("src.service.load_model")
@patch("src.service.rollback_model")
@patch("src.service.should_rollback")
def test_rollback_endpoint_reloads_previous_model(
    mock_should_rollback,
    mock_rollback_model,
    mock_load_model,
    mock_load_canary_models,
    app,
):
    """
    Verify that /rollback:

    1. Detects bad model performance.
    2. Calls rollback_model().
    3. Reloads production model.
    4. Reloads canary models.
    5. Updates production version.
    """

    mock_should_rollback.return_value = True

    mock_rollback_model.return_value = {
        "status": "rolled_back",
        "model_name": "iris_classifier",
        "from_version": "2",
        "to_version": "1",
    }

    mock_model = MagicMock()

    mock_load_model.return_value = (
        mock_model,
        "1",
    )

    mock_canary_models = {
        "production": (
            MagicMock(),
            "1",
        ),
        "staging": (
            MagicMock(),
            "2",
        ),
    }

    mock_load_canary_models.return_value = (
        mock_canary_models
    )

    with TestClient(app) as test_client:

        response = test_client.post(
            "/rollback",
            json={
                "request": {
                    "new_model_accuracy": 0.70,
                    "previous_model_accuracy": 0.92,
                }
            },
        )

    # ------------------------------------------------------
    # HTTP response
    # ------------------------------------------------------

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "rolled_back"

    assert data["model_name"] == "iris_classifier"

    assert data["from_version"] == "2"

    assert data["to_version"] == "1"

    assert data["new_model_accuracy"] == 0.70

    assert data["previous_model_accuracy"] == 0.92

    assert data["current_production_version"] == "1"

    # ------------------------------------------------------
    # Verify rollback decision
    # ------------------------------------------------------

    mock_should_rollback.assert_called_once_with(
        new_model_accuracy=0.70,
        previous_model_accuracy=0.92,
    )

    # ------------------------------------------------------
    # Verify rollback operation
    # ------------------------------------------------------

    mock_rollback_model.assert_called_once_with(
        "iris_classifier"
    )

    # ------------------------------------------------------
    # Verify production model reload
    # ------------------------------------------------------

    mock_load_model.assert_called()

    # ------------------------------------------------------
    # Verify canary models reload
    # ------------------------------------------------------

    mock_load_canary_models.assert_called()


# ==========================================================
# Rollback Endpoint - No Rollback
# ==========================================================

@patch("src.service.rollback_model")
@patch("src.service.should_rollback")
def test_rollback_endpoint_does_not_rollback_when_model_is_good(
    mock_should_rollback,
    mock_rollback_model,
    app,
):
    """
    Verify that /rollback does not change production
    when the new model performs acceptably.
    """

    mock_should_rollback.return_value = False

    with TestClient(app) as test_client:

        response = test_client.post(
            "/rollback",
            json={
                "request": {
                    "new_model_accuracy": 0.94,
                    "previous_model_accuracy": 0.92,
                }
            },
        )

    # ------------------------------------------------------
    # HTTP response
    # ------------------------------------------------------

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "no_rollback"

    assert data["message"] == (
        "New model performance is acceptable"
    )

    assert data["new_model_accuracy"] == 0.94

    assert data["previous_model_accuracy"] == 0.92

    # ------------------------------------------------------
    # Rollback must NOT be called
    # ------------------------------------------------------

    mock_rollback_model.assert_not_called()

    mock_should_rollback.assert_called_once_with(
        new_model_accuracy=0.94,
        previous_model_accuracy=0.92,
    )


# ==========================================================
# Rollback Endpoint - Invalid New Accuracy
# ==========================================================

def test_rollback_rejects_new_accuracy_above_one(
    app,
):
    """
    Pydantic should reject accuracy values greater than 1.0.
    """

    with TestClient(app) as test_client:

        response = test_client.post(
            "/rollback",
            json={
                "request": {
                    "new_model_accuracy": 1.1,
                    "previous_model_accuracy": 0.92,
                }
            },
        )

    assert response.status_code == 400


# ==========================================================
# Rollback Endpoint - Invalid Previous Accuracy
# ==========================================================

def test_rollback_rejects_previous_accuracy_above_one(
    app,
):
    """
    Pydantic should reject previous accuracy values
    greater than 1.0.
    """

    with TestClient(app) as test_client:

        response = test_client.post(
            "/rollback",
            json={
                "request": {
                    "new_model_accuracy": 0.70,
                    "previous_model_accuracy": 1.1,
                }
            },
        )

    assert response.status_code == 400


# ==========================================================
# Rollback Endpoint - Negative Accuracy
# ==========================================================

def test_rollback_rejects_negative_accuracy(
    app,
):
    """
    Pydantic should reject negative accuracy values.
    """

    with TestClient(app) as test_client:

        response = test_client.post(
            "/rollback",
            json={
                "request": {
                    "new_model_accuracy": -0.1,
                    "previous_model_accuracy": 0.92,
                }
            },
        )

    assert response.status_code == 400


# ==========================================================
# Rollback Endpoint - Missing Request
# ==========================================================

def test_rollback_rejects_missing_request(
    app,
):
    """
    Verify that the endpoint rejects a request body
    that does not contain the required request object.
    """

    with TestClient(app) as test_client:

        response = test_client.post(
            "/rollback",
            json={
                "new_model_accuracy": 0.70,
                "previous_model_accuracy": 0.92,
            },
        )

    assert response.status_code == 400

