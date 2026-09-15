import os
from pathlib import Path

import joblib
import mlflow.sklearn
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from src.config import MODEL_NAME

client = MlflowClient()


def load_model():
    """
    Load the Production model.

    Docker:
        Load bundled model from /app/models/model.pkl.

    Local development:
        Load Production model from MLflow Registry.
    """

    # --------------------------------------------------
    # Docker environment
    # --------------------------------------------------

    local_model_path = Path("/app/models/model.pkl")

    if local_model_path.exists():

        model = joblib.load(local_model_path)

        try:
            model_version = client.get_model_version_by_alias(
                MODEL_NAME,
                "production",
            ).version
        except Exception:
            model_version = "local"

        return model, str(model_version)

    # --------------------------------------------------
    # Local development / MLflow
    # --------------------------------------------------

    model_uri = f"models:/{MODEL_NAME}@production"

    try:

        model = mlflow.sklearn.load_model(model_uri)

        model_version = client.get_model_version_by_alias(
            MODEL_NAME,
            "production",
        ).version

    except MlflowException as exc:

        raise RuntimeError(
            f"No model is promoted to @production for '{MODEL_NAME}'. "
            "Run `python -m src.train` or promote an existing "
            "staging version."
        ) from exc

    return model, str(model_version)


def get_model_version():

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
    print("=" * 60)