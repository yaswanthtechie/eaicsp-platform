
"""
Production model loading utilities.

Local development:
    Load the model assigned to the MLflow @production alias.

BentoML container:
    Load the standalone model packaged inside the Bento.

The BentoML bundled-model behavior is enabled explicitly through
the BENTO_BUNDLED_MODEL environment variable so that the existence
of models/model.pkl in the local repository does not bypass MLflow.
"""

import os
from pathlib import Path

import joblib
import mlflow.sklearn
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from src.config import MODEL_NAME


client = MlflowClient()


# ------------------------------------------------------------------
# BentoML bundled model configuration
# ------------------------------------------------------------------

BUNDLED_MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "models"
    / "model.pkl"
)


def is_bundled_model_enabled() -> bool:
    """
    Return True when bundled-model mode is explicitly enabled.

    BentoML containers should set:

        BENTO_BUNDLED_MODEL=true

    Local development does not set this variable, so normal
    MLflow production-alias loading is used.
    """

    return (
        os.getenv(
            "BENTO_BUNDLED_MODEL",
            "",
        )
        .strip()
        .lower()
        == "true"
    )


# ------------------------------------------------------------------
# Model loading
# ------------------------------------------------------------------

def load_model():
    """
    Load the Production model.

    BentoML container:
        When BENTO_BUNDLED_MODEL=true, load the standalone model
        packaged inside the Bento.

    Local development:
        Load the model currently assigned to the MLflow
        @production alias.

    Returns
    -------
    tuple
        (model, model_version)
    """

    # --------------------------------------------------------------
    # BentoML bundled-model mode
    # --------------------------------------------------------------

    if is_bundled_model_enabled():

        if not BUNDLED_MODEL_PATH.exists():
            raise RuntimeError(
                "Bento bundled-model mode is enabled, but the "
                f"model file was not found: {BUNDLED_MODEL_PATH}"
            )

        model = joblib.load(
            BUNDLED_MODEL_PATH
        )

        # The Bento container does not require the MLflow registry
        # to load the actual model. We only try to retrieve the
        # production version for metadata.
        try:

            model_version = (
                client
                .get_model_version_by_alias(
                    MODEL_NAME,
                    "production",
                )
                .version
            )

        except Exception:

            model_version = "local"

        return model, str(model_version)

    # --------------------------------------------------------------
    # Local development / MLflow Registry
    # --------------------------------------------------------------

    model_uri = (
        f"models:/{MODEL_NAME}@production"
    )

    try:

        # IMPORTANT:
        # Always load the model through the MLflow production alias.
        #
        # This guarantees that changing the @production alias changes
        # the model used by the application.
        model = mlflow.sklearn.load_model(
            model_uri
        )

        model_version = (
            client
            .get_model_version_by_alias(
                MODEL_NAME,
                "production",
            )
            .version
        )

    except MlflowException as exc:

        raise RuntimeError(
            f"No model is promoted to @production "
            f"for '{MODEL_NAME}'. "
            "Run `python -m src.train` or promote "
            "an existing staging version."
        ) from exc

    return model, str(model_version)


# ------------------------------------------------------------------
# Production model version
# ------------------------------------------------------------------

def get_model_version():
    """
    Return the version currently assigned to the MLflow
    @production alias.
    """

    version = (
        client
        .get_model_version_by_alias(
            MODEL_NAME,
            "production",
        )
        .version
    )

    return str(version)


# ------------------------------------------------------------------
# Command-line verification
# ------------------------------------------------------------------

if __name__ == "__main__":

    model, version = load_model()

    print("=" * 60)
    print("Production Model Loaded Successfully")
    print("=" * 60)

    print(
        f"Model Name    : {MODEL_NAME}"
    )

    print(
        f"Model Version : {version}"
    )

    print(
        f"Bundled Mode  : {is_bundled_model_enabled()}"
    )

    print("=" * 60)

