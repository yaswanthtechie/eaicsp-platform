"""
Prediction model loader.

This module loads the current Production model from the
MLflow Model Registry.

The service always loads the model using the Production alias,
so promoting a new version requires no code changes.
"""

import mlflow.sklearn
from mlflow.tracking import MlflowClient

from src.config import MODEL_NAME

client = MlflowClient()


def load_model():
    """
    Load the Production model from the MLflow Model Registry.

    Returns
    -------
    tuple
        (
            model,
            model_version
        )
    """

    model_uri = f"models:/{MODEL_NAME}@production"

    model = mlflow.sklearn.load_model(model_uri)

    model_version = client.get_model_version_by_alias(
        MODEL_NAME,
        "production",
    ).version

    return model, str(model_version)


def get_model_version():
    """
    Get the current Production model version.

    Returns
    -------
    str
        Production model version.
    """

    version = client.get_model_version_by_alias(
        MODEL_NAME,
        "production",
    ).version

    return str(version)


if __name__ == "__main__":

    model, version = load_model()

    print("=" * 60)
    print("Production Model Loaded Successfully")
    print("=" * 60)
    print(f"Model Name    : {MODEL_NAME}")
    print(f"Model Version : {version}")
    print(f"Model URI     : models:/{MODEL_NAME}@production")
    print("=" * 60)