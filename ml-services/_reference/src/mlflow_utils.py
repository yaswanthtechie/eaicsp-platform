"""
MLflow utility wrapper.

Reusable MLflow wrapper functions for all ML services.
"""

from contextlib import contextmanager

import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient


client = MlflowClient()


@contextmanager
def start_run(run_name: str | None = None):
    """
    Start an MLflow run.
    """
    with mlflow.start_run(run_name=run_name):
        yield


def set_experiment(experiment_name: str) -> None:
    """
    Set MLflow experiment.
    """
    mlflow.set_experiment(experiment_name)


def log_params(params: dict) -> None:
    """
    Log parameters.
    """
    if params:
        mlflow.log_params(params)


def log_metrics(metrics: dict) -> None:
    """
    Log metrics.
    """
    if metrics:
        mlflow.log_metrics(metrics)


def log_model(
    model,
    artifact_path: str,
    registered_model_name: str | None = None,
):
    """
    Log and register a model.
    """
    return mlflow.sklearn.log_model(
        sk_model=model,
        artifact_path=artifact_path,
        registered_model_name=registered_model_name,
    )


def set_tags(tags: dict) -> None:
    """
    Set MLflow tags.
    """
    if tags:
        mlflow.set_tags(tags)


def log_artifact(file_path: str) ->None:
    """
    Log artifact.
    """
    mlflow.log_artifact(file_path)


def promote_model(model_name: str) -> str:
    """
    Promote the latest registered model to the
    'production' alias.

    Returns
    -------
    str
        Latest model version.
    """

    versions = client.search_model_versions(
        f"name='{model_name}'"
    )

    if not versions:
        raise Exception(f"No versions found for '{model_name}'.")

    latest = max(
        versions,
        key=lambda mv: int(mv.version),
    )

    client.set_registered_model_alias(
        name=model_name,
        alias="production",
        version=latest.version,
    )

    print(
        f"Model '{model_name}' Version "
        f"{latest.version} promoted to @production"
    )

    return latest.version