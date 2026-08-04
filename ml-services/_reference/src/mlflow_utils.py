"""
MLflow utility wrapper.

Reusable helper functions for:
- Experiment management
- Run management
- Parameter logging
- Metric logging
- Model registration
- Staging and Production alias promotion
"""

from contextlib import contextmanager

import mlflow
import mlflow.sklearn

from mlflow.tracking import MlflowClient


client = MlflowClient()


# ==========================================================
# Experiment
# ==========================================================

def set_experiment(experiment_name: str) -> None:
    """
    Create or set an MLflow experiment.
    """

    mlflow.set_experiment(experiment_name)



# ==========================================================
# Run
# ==========================================================

@contextmanager
def start_run(run_name: str | None = None):
    """
    Start MLflow run.
    """

    with mlflow.start_run(run_name=run_name):
        yield



# ==========================================================
# Logging
# ==========================================================

def log_params(params: dict) -> None:
    """
    Log model parameters.
    """

    if params:
        mlflow.log_params(params)



def log_metrics(metrics: dict) -> None:
    """
    Log evaluation metrics.
    """

    if metrics:
        mlflow.log_metrics(metrics)



def log_artifact(file_path: str):
    """
    Log artifacts.
    """

    mlflow.log_artifact(file_path)



def set_tags(tags: dict):
    """
    Add MLflow tags.
    """

    if tags:
        mlflow.set_tags(tags)



# ==========================================================
# Model Registration
# ==========================================================

def log_model(
    model,
    artifact_path: str,
    registered_model_name: str,
):
    """
    Log and register sklearn model.

    Returns
    -------
    ModelInfo
    """

    return mlflow.sklearn.log_model(
        sk_model=model,
        artifact_path=artifact_path,
        registered_model_name=registered_model_name,
    )



# ==========================================================
# Registry Helpers
# ==========================================================

def get_latest_version(model_name: str):
    """
    Get latest registered model version.
    """

    versions = client.search_model_versions(
        f"name='{model_name}'"
    )

    if not versions:
        raise Exception(
            f"No versions found for {model_name}"
        )

    return max(
        versions,
        key=lambda x: int(x.version),
    )



def get_model_version_by_alias(
    model_name: str,
    alias: str,
):
    """
    Get model version using alias.
    """

    try:

        version = client.get_model_version_by_alias(
            model_name,
            alias,
        )

        return version.version

    except Exception:

        return None



# ==========================================================
# Staging Workflow
# ==========================================================

def assign_staging(
    model_name: str,
):
    """
    Assign latest registered model
    to staging alias.

    Flow:

    Register Version
          |
          v
       staging
    """

    latest = get_latest_version(
        model_name
    )


    client.set_registered_model_alias(
        name=model_name,
        alias="staging",
        version=latest.version,
    )


    print("=" * 60)
    print("STAGING ASSIGNED")
    print("=" * 60)
    print(f"Model Name : {model_name}")
    print(f"Version    : {latest.version}")
    print("Alias      : @staging")
    print("=" * 60)


    return latest.version



# ==========================================================
# Production Promotion
# ==========================================================

def promote_model(
    model_name: str,
    from_alias: str = "staging",
    to_alias: str = "production",
):
    """
    Promote model between aliases.

    Example:

    @staging
        |
        |
        v
    @production

    """

    version = client.get_model_version_by_alias(
        model_name,
        from_alias,
    )


    old_production = get_model_version_by_alias(
        model_name,
        to_alias,
    )


    client.set_registered_model_alias(
        name=model_name,
        alias=to_alias,
        version=version.version,
    )


    print("=" * 60)
    print("MODEL PROMOTED")
    print("=" * 60)

    print(f"Model Name      : {model_name}")
    print(f"Version         : {version.version}")
    print(f"From Alias      : @{from_alias}")
    print(f"To Alias        : @{to_alias}")

    if old_production:
        print(
            f"Old Production : {old_production}"
        )

    print("=" * 60)


    return version.version



# ==========================================================
# Load Production Model
# ==========================================================

def load_production_model(
    model_name: str,
):
    """
    Load production model.

    Uses alias,
    not file path.
    """

    model_uri = (
        f"models:/{model_name}@production"
    )


    model = mlflow.sklearn.load_model(
        model_uri
    )


    version = client.get_model_version_by_alias(
        model_name,
        "production",
    ).version


    return model, str(version)



# ==========================================================
# Registry Info
# ==========================================================

def list_versions(model_name: str):
    """
    Display all model versions.
    """

    versions = client.search_model_versions(
        f"name='{model_name}'"
    )


    for version in versions:

        print(
            f"Version : {version.version}"
        )



def current_production(model_name: str):

    """
    Display current production version.
    """

    version = get_model_version_by_alias(
        model_name,
        "production",
    )


    print(
        f"Production Version : {version}"
    )


    return version