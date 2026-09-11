"""
Tests for the model registry promotion workflow.

Verifies:

1. Staging -> Production promotion
2. Promotion auditing
3. Prediction follows the production alias
4. Promotion of a non-existent version fails
5. Production -> Staging demotion
"""

from unittest import mock

import pytest

from src.config import MODEL_NAME


@pytest.fixture
def fake_client():
    with mock.patch("src.mlflow_utils.client") as m:
        yield m


# ==========================================================
# Normal Promotion
# ==========================================================

def test_promote_model_points_production_alias_at_staging_version(
    fake_client,
):
    """
    @staging is on v2.

    Promotion should move @production to v2.
    """

    from src.mlflow_utils import promote_model

    fake_client.get_model_version_by_alias.return_value = mock.Mock(
        version="2"
    )

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


# ==========================================================
# Promotion Audit
# ==========================================================

def test_promotion_is_audited(fake_client):
    """
    Promotion must record who performed the promotion
    and when it happened.
    """

    from src.mlflow_utils import promote_model

    fake_client.get_model_version_by_alias.return_value = mock.Mock(
        version="2"
    )

    promote_model(MODEL_NAME)

    tagged = {
        call.kwargs["key"]
        for call in fake_client.set_model_version_tag.call_args_list
    }

    assert "promoted_by" in tagged
    assert "promotion_time" in tagged


# ==========================================================
# Prediction Uses Production Alias
# ==========================================================

def test_predict_follows_the_alias_not_a_hardcoded_path():
    """
    Prediction should load whatever model version is
    currently assigned to @production.
    """

    import src.predict as predict

    with mock.patch.object(
        predict,
        "client",
    ) as fake, mock.patch(
        "mlflow.sklearn.load_model"
    ) as fake_load:

        fake_load.return_value = "model-v2"

        fake.get_model_version_by_alias.return_value = mock.Mock(
            version="2"
        )

        model, version = predict.load_model()

    assert version == "2"

    fake_load.assert_called_once_with(
        f"models:/{MODEL_NAME}@production"
    )


# ==========================================================
# R4 Promotion Edge Case
# ==========================================================

def test_promote_nonexistent_version_fails(fake_client):
    """
    Promotion should fail when the source alias/version
    does not exist.
    """

    from src.mlflow_utils import promote_model

    fake_client.get_model_version_by_alias.side_effect = Exception(
        "Model version not found"
    )

    with pytest.raises(
        Exception,
        match="Model version not found",
    ):
        promote_model(
            MODEL_NAME,
            from_alias="staging",
            to_alias="production",
        )


# ==========================================================
# R4 Production -> Staging Demotion
# ==========================================================

def test_demote_production_back_to_staging(fake_client):
    """
    Production model should be able to move back to Staging.
    """

    from src.mlflow_utils import promote_model

    fake_client.get_model_version_by_alias.return_value = mock.Mock(
        version="2"
    )

    promoted = promote_model(
        MODEL_NAME,
        from_alias="production",
        to_alias="staging",
    )

    assert promoted == "2"

    fake_client.set_registered_model_alias.assert_called_once_with(
        name=MODEL_NAME,
        alias="staging",
        version="2",
    )