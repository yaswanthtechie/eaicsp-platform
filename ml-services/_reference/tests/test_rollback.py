
"""
R5 rollback tests.

Covers:

1. Rollback decision logic.
2. Successful MLflow rollback.
3. Missing previous production version.
4. Previous version equals current version.
5. /rollback endpoint reloads the previous model.
6. /rollback endpoint does not rollback a good model.
"""

from unittest.mock import MagicMock, call, patch

import pytest
from starlette.testclient import TestClient

from src.rollback import should_rollback
from src.mlflow_utils import rollback_model
from src.service import IrisService


# ==========================================================
# Rollback Decision Tests
# ==========================================================


def test_rollback_when_new_model_is_worse():

    result = should_rollback(
        new_model_accuracy=0.70,
        previous_model_accuracy=0.92,
    )

    assert result is True


def test_no_rollback_when_new_model_is_better():

    result = should_rollback(
        new_model_accuracy=0.94,
        previous_model_accuracy=0.92,
    )

    assert result is False


def test_rollback_when_below_minimum_accuracy():

    result = should_rollback(
        new_model_accuracy=0.80,
        previous_model_accuracy=0.85,
        minimum_accuracy=0.85,
    )

    assert result is True


# ==========================================================
# MLflow Rollback Tests
# ==========================================================


@patch("src.mlflow_utils._set_alias")
@patch("src.mlflow_utils.client")
def test_rollback_model_success(
    mock_client,
    mock_set_alias,
):
    """
    Verify successful restoration of the previous
    production model version.
    """

    current_version = MagicMock()

    current_version.version = "2"

    current_version.tags = {
        "previous_production_version": "1"
    }

    mock_client.get_model_version_by_alias.return_value = (
        current_version
    )

    mock_client.get_model_version.return_value = (
        current_version
    )

    result = rollback_model(
        "iris_classifier"
    )

    assert result["status"] == "rolled_back"

    assert result["model_name"] == (
        "iris_classifier"
    )

    assert result["from_version"] == "2"

    assert result["to_version"] == "1"

    mock_set_alias.assert_called_once_with(
        "iris_classifier",
        "production",
        "1",
    )

    assert (
        mock_client.set_model_version_tag.call_count
        == 2
    )


@patch("src.mlflow_utils.client")
def test_rollback_model_without_previous_version(
    mock_client,
):
    """
    Rollback must fail when the current production
    version does not contain a previous version tag.
    """

    current_version = MagicMock()

    current_version.version = "2"

    current_version.tags = {}

    mock_client.get_model_version_by_alias.return_value = (
        current_version
    )

    mock_client.get_model_version.return_value = (
        current_version
    )

    with pytest.raises(
        RuntimeError,
        match="No previous production version",
    ):
        rollback_model(
            "iris_classifier"
        )


@patch("src.mlflow_utils.client")
def test_rollback_model_previous_equals_current(
    mock_client,
):
    """
    Rollback must fail when previous production
    version is the same as the current version.
    """

    current_version = MagicMock()

    current_version.version = "2"

    current_version.tags = {
        "previous_production_version": "2"
    }

    mock_client.get_model_version_by_alias.return_value = (
        current_version
    )

    mock_client.get_model_version.return_value = (
        current_version
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Previous production version cannot be "
            "the current production version"
        ),
    ):
        rollback_model(
            "iris_classifier"
        )


# ==========================================================
# BentoML Application
# ==========================================================

# Create the BentoML ASGI application once.
#
# Creating multiple BentoML TestClient instances can cause
# Prometheus DuplicateTimeseries errors because BentoML
# registers the same metrics more than once.

APP = IrisService.to_asgi()


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
        "production": MagicMock(),
        "staging": MagicMock(),
    }

    mock_load_canary_models.return_value = (
        mock_canary_models
    )

    with TestClient(APP) as test_client:

        response = test_client.post(
            "/rollback",
            json={
                "new_model_accuracy": 0.70,
                "previous_model_accuracy": 0.92,
            },
        )

    # ------------------------------------------------------
    # HTTP response
    # ------------------------------------------------------

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == (
        "rolled_back"
    )

    assert body["from_version"] == "2"

    assert body["to_version"] == "1"

    assert body["new_model_accuracy"] == 0.70

    assert body["previous_model_accuracy"] == 0.92

    assert body[
        "current_production_version"
    ] == "1"

    # ------------------------------------------------------
    # Rollback decision
    # ------------------------------------------------------

    mock_should_rollback.assert_called_once_with(
        new_model_accuracy=0.70,
        previous_model_accuracy=0.92,
    )

    # ------------------------------------------------------
    # MLflow rollback
    # ------------------------------------------------------

    mock_rollback_model.assert_called_once_with(
        "iris_classifier"
    )

    # ------------------------------------------------------
    # Model reload
    # ------------------------------------------------------

    # load_model() may be called during BentoML service
    # initialization and again after rollback.
    assert mock_load_model.call_count >= 1

    # The final call must be the post-rollback reload.
    assert (
        mock_load_model.call_args_list[-1]
        == call()
    )

    # ------------------------------------------------------
    # Canary reload
    # ------------------------------------------------------

    assert (
        mock_load_canary_models.call_count
        >= 1
    )


# ==========================================================
# Rollback Endpoint - No Rollback
# ==========================================================


@patch("src.service.rollback_model")
@patch("src.service.should_rollback")
def test_rollback_endpoint_does_not_rollback_when_model_is_good(
    mock_should_rollback,
    mock_rollback_model,
):
    """
    Verify that /rollback does not change production
    when the new model performs acceptably.
    """

    mock_should_rollback.return_value = False

    with TestClient(APP) as test_client:

        response = test_client.post(
            "/rollback",
            json={
                "new_model_accuracy": 0.94,
                "previous_model_accuracy": 0.92,
            },
        )

    # ------------------------------------------------------
    # HTTP response
    # ------------------------------------------------------

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == (
        "no_rollback"
    )

    assert body["new_model_accuracy"] == 0.94

    assert body[
        "previous_model_accuracy"
    ] == 0.92

    # ------------------------------------------------------
    # Rollback decision
    # ------------------------------------------------------

    mock_should_rollback.assert_called_once_with(
        new_model_accuracy=0.94,
        previous_model_accuracy=0.92,
    )

    # ------------------------------------------------------
    # No MLflow rollback
    # ------------------------------------------------------

    mock_rollback_model.assert_not_called()

