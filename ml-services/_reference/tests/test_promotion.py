"""
Tests for the model registry promotion workflow.

Verifies the core guarantee: once a version is promoted to
@production, predict.load_model() picks it up with no code change.

MlflowClient is mocked so these run without a live tracking server.
"""

from unittest import mock

import pytest

from src.config import MODEL_NAME


@pytest.fixture
def fake_client():
    with mock.patch("src.mlflow_utils.client") as m:
        yield m


def test_promote_model_points_production_alias_at_staging_version(fake_client):
    """@staging is on v2 -> promoting must move @production to v2."""
    from src.mlflow_utils import promote_model

    fake_client.get_model_version_by_alias.return_value = mock.Mock(version="2")

    promoted = promote_model(
        MODEL_NAME,
        from_alias="staging",
        to_alias="production",
    )

    assert promoted == "2"

    fake_client.set_registered_model_alias.assert_called_once_with(
        name=MODEL_NAME,
        alias="production",
        version="2",
    )


def test_promotion_is_audited(fake_client):
    """Promotion must record who did it and when."""
    from src.mlflow_utils import promote_model

    fake_client.get_model_version_by_alias.return_value = mock.Mock(version="2")

    promote_model(MODEL_NAME)

    tagged = {
        call.kwargs["key"]
        for call in fake_client.set_model_version_tag.call_args_list
    }

    assert "promoted_by" in tagged
    assert "promotion_time" in tagged


def test_predict_follows_the_alias_not_a_hardcoded_path():
    """The zero-code-change claim: load_model serves whatever @production points at."""
    import src.predict as predict

    with mock.patch.object(predict, "client") as fake, \
         mock.patch("mlflow.sklearn.load_model") as fake_load:

        fake_load.return_value = "model-v2"
        fake.get_model_version_by_alias.return_value = mock.Mock(version="2")

        model, version = predict.load_model()

    assert version == "2"
    fake_load.assert_called_once_with(f"models:/{MODEL_NAME}@production")