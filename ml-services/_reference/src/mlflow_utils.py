
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
from datetime import datetime, timezone

import mlflow
import mlflow.sklearn

from mlflow.tracking import MlflowClient

from src.config import PROMOTED_BY


client = MlflowClient()


# ==========================================================
# Alias Helper
# ==========================================================

def _set_alias(
    model_name: str,
    alias: str,
    version: str,
) -> None:
    """
    Set an alias for a registered model version.

    Tries MLflow's newer alias API first.
    Falls back to transition_model_version_stage
    if the alias API is unavailable.
    """

    # Prefer the newer alias API
    try:
        if hasattr(client, "set_registered_model_alias"):
            client.set_registered_model_alias(
                name=model_name,
                alias=alias,
                version=version,
            )
            return
    except Exception:
        # If the API exists but fails, expose the error
        raise

    # Fallback: map alias to stage name
    stage = alias.capitalize()

    if hasattr(client, "transition_model_version_stage"):
        client.transition_model_version_stage(
            name=model_name,
            version=version,
            stage=stage,
            archive_existing_versions=False,
        )
        return

    raise RuntimeError(
        "Cannot set alias: Mlflow client has neither "
        "'set_registered_model_alias' nor "
        "'transition_model_version_stage'."
    )


# ==========================================================
# Experiment
# ==========================================================

def set_experiment(
    experiment_name: str,
) -> None:
    """
    Create or set an MLflow experiment.
    """

    mlflow.set_experiment(experiment_name)


# ==========================================================
# Run
# ==========================================================

@contextmanager
def start_run(
    run_name: str | None = None,
):
    """
    Start MLflow run.
    """

    with mlflow.start_run(run_name=run_name):
        yield


# ==========================================================
# Logging
# ==========================================================

def log_params(
    params: dict,
) -> None:
    """
    Log model parameters.
    """

    if params:
        mlflow.log_params(params)


def log_metrics(
    metrics: dict,
) -> None:
    """
    Log evaluation metrics.
    """

    if metrics:
        mlflow.log_metrics(metrics)


def log_artifact(
    file_path: str,
):
    """
    Log artifacts.
    """

    mlflow.log_artifact(file_path)


def set_tags(
    tags: dict,
):
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

def get_latest_version(
    model_name: str,
):
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
    Get model version string for a given alias,
    or None if the alias is not present.
    """

    try:
        mv = client.get_model_version_by_alias(
            model_name,
            alias,
        )

        return mv.version if mv is not None else None

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

    _set_alias(
        model_name,
        "staging",
        latest.version,
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
    Promote a model version from one alias to another.

    Records the previous target-alias version before
    changing the target alias and adds promotion metadata.
    """

    # --------------------------------------------------
    # Get source model version
    # --------------------------------------------------

    source_version = client.get_model_version_by_alias(
        model_name,
        from_alias,
    )

    if source_version is None:
        raise RuntimeError(
            f"No version found for alias '{from_alias}' "
            f"on registered model '{model_name}'."
        )

    new_version = str(source_version.version)

    # --------------------------------------------------
    # Get current target alias version
    # --------------------------------------------------
    #
    # Do not use get_model_version_by_alias() here because
    # tests/mock clients may configure the underlying MLflow
    # client directly.
    # --------------------------------------------------

    target_version = None

    try:
        current_target = client.get_model_version_by_alias(
            model_name,
            to_alias,
        )

        if current_target is not None:
            target_version = str(current_target.version)

    except Exception:
        target_version = None

    # --------------------------------------------------
    # Prevent assigning the same version to the same alias
    # --------------------------------------------------

    if (
        target_version is not None
        and new_version == target_version
        and from_alias == to_alias
    ):
        raise RuntimeError(
            f"Version {new_version} is already "
            f"the current {to_alias} version."
        )

    # --------------------------------------------------
    # Save previous target version
    # --------------------------------------------------

    if (
        target_version is not None
        and new_version != target_version
    ):
        client.set_model_version_tag(
            name=model_name,
            version=new_version,
            key=f"previous_{to_alias}_version",
            value=target_version,
        )

    # --------------------------------------------------
    # Set target alias
    # --------------------------------------------------

    _set_alias(
        model_name,
        to_alias,
        new_version,
    )

    # --------------------------------------------------
    # Promotion metadata
    # --------------------------------------------------

    client.set_model_version_tag(
        name=model_name,
        version=new_version,
        key="promoted_by",
        value=PROMOTED_BY,
    )

    client.set_model_version_tag(
        name=model_name,
        version=new_version,
        key="promotion_time",
        value=datetime.now(timezone.utc).isoformat(),
    )

    # --------------------------------------------------
    # Output
    # --------------------------------------------------

    print("=" * 60)
    print("MODEL PROMOTED")
    print("=" * 60)

    print(f"Model Name : {model_name}")
    print(f"Version    : {new_version}")
    print(f"From Alias : @{from_alias}")
    print(f"To Alias   : @{to_alias}")

    if target_version and target_version != new_version:
        print(
            f"Previous {to_alias.capitalize()} : "
            f"{target_version}"
        )

    print("=" * 60)

    return new_version



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

def list_versions(
    model_name: str,
):
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


def current_production(
    model_name: str,
):
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
# ==========================================================
# Rollback Info
# ==========================================================

def rollback_model(
    model_name: str,
):
    """
    Roll Production back to the previous production version.
    """

    current_version = get_model_version_by_alias(
        model_name,
        "production",
    )

    if current_version is None:
        raise RuntimeError(
            f"No production version found for {model_name}"
        )

    current_version = str(
        current_version
    )

    current = client.get_model_version(
        name=model_name,
        version=current_version,
    )

    previous_version = current.tags.get(
        "previous_production_version"
    )

    if not previous_version:
        raise RuntimeError(
            "No previous production version "
            f"recorded for model {model_name}"
        )

    previous_version = str(
        previous_version
    )

    if previous_version == current_version:
        raise RuntimeError(
            "Previous production version cannot "
            "be the current production version"
        )

    # Restore previous Production alias.
    _set_alias(
        model_name,
        "production",
        previous_version,
    )

    # Record rollback information.
    client.set_model_version_tag(
        name=model_name,
        version=current_version,
        key="rollback_status",
        value="rolled_back",
    )

    client.set_model_version_tag(
        name=model_name,
        version=current_version,
        key="rollback_to_version",
        value=previous_version,
    )

    print("=" * 60)
    print("MODEL ROLLBACK COMPLETED")
    print("=" * 60)
    print(
        f"Model Name       : {model_name}"
    )
    print(
        f"Failed Version   : {current_version}"
    )
    print(
        f"Restored Version : {previous_version}"
    )
    print("=" * 60)

    return {
        "status": "rolled_back",
        "model_name": model_name,
        "from_version": current_version,
        "to_version": previous_version,
    }
