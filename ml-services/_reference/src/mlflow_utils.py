"""
MLflow utility wrapper.

Reusable helper functions for:

- Experiment management
- Run management
- Parameter logging
- Metric logging
- Model registration
- Staging and Production alias promotion
- Governance audit tagging
- Model rollback
"""

from contextlib import contextmanager
from datetime import datetime, timezone

import mlflow
import mlflow.sklearn

from mlflow.tracking import MlflowClient

from src.config import PROMOTED_BY


client = MlflowClient()


# ==========================================================
# Governance Helper
# ==========================================================


def _default_governance():
    """
    Return the default governance manager.

    Imported lazily so mlflow_utils has no import-time
    dependency on governance storage.
    """

    from src.governance import governance_manager

    return governance_manager


# ==========================================================
# Governance Audit Tags
# ==========================================================


def record_governance_decision(
    model_name: str,
    model_version: str,
    approver: str,
    decision: str,
    decision_time: str,
    reason: str = "",
) -> None:
    """
    Record a governance decision directly on an MLflow
    model version.

    The application governance state remains persisted in
    governance.json, while MLflow stores the same decision
    as model-version metadata.

    Tags recorded:

        governance_approver
        governance_decision
        governance_decision_time
        governance_decision_reason

    Parameters
    ----------
    model_name:
        Registered MLflow model name.

    model_version:
        Exact MLflow model version.

    approver:
        Person who approved or rejected the model.

    decision:
        Either "approved" or "rejected".

    decision_time:
        UTC timestamp of the governance decision.

    reason:
        Optional approval/rejection reason.

    Notes
    -----
    This function intentionally allows MLflow exceptions to
    propagate to the caller.

    governance.py handles these exceptions because local
    governance state must remain available even when a
    logical/test model version is not registered in MLflow.
    """

    # ------------------------------------------------------
    # Validate model name
    # ------------------------------------------------------

    if not model_name:
        raise ValueError(
            "model_name is required"
        )

    # ------------------------------------------------------
    # Validate model version
    # ------------------------------------------------------

    if not model_version:
        raise ValueError(
            "model_version is required"
        )

    # ------------------------------------------------------
    # Validate approver
    # ------------------------------------------------------

    if not approver:
        raise ValueError(
            "approver is required"
        )

    # ------------------------------------------------------
    # Validate decision time
    # ------------------------------------------------------

    if not decision_time:
        raise ValueError(
            "decision_time is required"
        )

    # ------------------------------------------------------
    # Normalize decision
    # ------------------------------------------------------

    normalized_decision = (
        str(decision)
        .strip()
        .lower()
    )

    if normalized_decision not in {
        "approved",
        "rejected",
    }:
        raise ValueError(
            "decision must be 'approved' "
            "or 'rejected'"
        )

    model_version = str(
        model_version
    )

    # ------------------------------------------------------
    # Governance approver
    # ------------------------------------------------------

    client.set_model_version_tag(
        name=model_name,
        version=model_version,
        key="governance_approver",
        value=str(approver),
    )

    # ------------------------------------------------------
    # Governance decision
    # ------------------------------------------------------

    client.set_model_version_tag(
        name=model_name,
        version=model_version,
        key="governance_decision",
        value=normalized_decision,
    )

    # ------------------------------------------------------
    # Governance decision timestamp
    # ------------------------------------------------------

    client.set_model_version_tag(
        name=model_name,
        version=model_version,
        key="governance_decision_time",
        value=str(decision_time),
    )

    # ------------------------------------------------------
    # Governance decision reason
    # ------------------------------------------------------

    if reason:
        client.set_model_version_tag(
            name=model_name,
            version=model_version,
            key="governance_decision_reason",
            value=str(reason),
        )


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

    # ------------------------------------------------------
    # Prefer MLflow's alias API
    # ------------------------------------------------------

    try:
        if hasattr(
            client,
            "set_registered_model_alias",
        ):
            client.set_registered_model_alias(
                name=model_name,
                alias=alias,
                version=version,
            )
            return

    except Exception:
        # If the API exists but fails, expose the error.
        raise

    # ------------------------------------------------------
    # Fallback to model stage
    # ------------------------------------------------------

    stage = alias.capitalize()

    if hasattr(
        client,
        "transition_model_version_stage",
    ):
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

    mlflow.set_experiment(
        experiment_name
    )


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

    with mlflow.start_run(
        run_name=run_name
    ):
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
        mlflow.log_params(
            params
        )


def log_metrics(
    metrics: dict,
) -> None:
    """
    Log evaluation metrics.
    """

    if metrics:
        mlflow.log_metrics(
            metrics
        )


def log_artifact(
    file_path: str,
):
    """
    Log artifacts.
    """

    return mlflow.log_artifact(
        file_path
    )


def set_tags(
    tags: dict,
):
    """
    Add MLflow tags.
    """

    if tags:
        mlflow.set_tags(
            tags
        )


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

        return (
            mv.version
            if mv is not None
            else None
        )

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

    print(
        f"Model Name : {model_name}"
    )

    print(
        f"Version    : {latest.version}"
    )

    print(
        "Alias      : @staging"
    )

    print("=" * 60)

    return latest.version


# ==========================================================
# Production Promotion
# ==========================================================


def promote_model(
    model_name: str,
    from_alias: str = "staging",
    to_alias: str = "production",
    expected_version: str | None = None,
    governance=None,
):
    """
    Promote a model version from one alias to another.

    Parameters
    ----------
    model_name:
        Registered MLflow model name.

    from_alias:
        Source alias. Defaults to "staging".

    to_alias:
        Target alias. Defaults to "production".

    expected_version:
        Optional exact model version that is expected to be
        behind the source alias.

        This protects the governance workflow from
        accidentally promoting a different version if the
        staging alias changed after approval.

    governance:
        Optional governance manager used for dependency
        injection in tests or specialized workflows.

        When omitted, the default governance manager is
        loaded lazily.

    Raises
    ------
    RuntimeError
        If the source alias does not exist.

    RuntimeError
        If expected_version is supplied and does not match
        the current source alias version.

    PermissionError
        If production promotion is requested without
        governance approval for the exact model version.
    """

    # ------------------------------------------------------
    # Get source model version
    # ------------------------------------------------------

    source_version = (
        client.get_model_version_by_alias(
            model_name,
            from_alias,
        )
    )

    if source_version is None:
        raise RuntimeError(
            f"No version found for alias "
            f"'{from_alias}' on registered "
            f"model '{model_name}'."
        )

    new_version = str(
        source_version.version
    )

    # ------------------------------------------------------
    # Exact version safety check
    # ------------------------------------------------------

    if (
        expected_version is not None
        and new_version != str(
            expected_version
        )
    ):
        raise RuntimeError(
            f"Version mismatch: expected version "
            f"{expected_version} behind @{from_alias}, "
            f"but found version {new_version}."
        )

    # ------------------------------------------------------
    # Governance gate
    # ------------------------------------------------------

    if to_alias == "production":

        gate = (
            governance
            if governance is not None
            else _default_governance()
        )

        gate.require_approval(
            model_name=model_name,
            model_version=new_version,
        )

    # ------------------------------------------------------
    # Get current target alias version
    # ------------------------------------------------------

    target_version = None

    try:

        current_target = (
            client.get_model_version_by_alias(
                model_name,
                to_alias,
            )
        )

        if current_target is not None:
            target_version = str(
                current_target.version
            )

    except Exception:
        target_version = None

    # ------------------------------------------------------
    # Prevent assigning the same version to the same alias
    # ------------------------------------------------------

    if (
        target_version is not None
        and new_version == target_version
        and from_alias == to_alias
    ):
        raise RuntimeError(
            f"Version {new_version} is already "
            f"the current {to_alias} version."
        )

    # ------------------------------------------------------
    # Save previous target version
    # ------------------------------------------------------

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

    # ------------------------------------------------------
    # Set target alias
    # ------------------------------------------------------

    _set_alias(
        model_name,
        to_alias,
        new_version,
    )

    # ------------------------------------------------------
    # Promotion metadata
    # ------------------------------------------------------

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
        value=datetime.now(
            timezone.utc
        ).isoformat(),
    )

    # ------------------------------------------------------
    # Output
    # ------------------------------------------------------

    print("=" * 60)
    print("MODEL PROMOTED")
    print("=" * 60)

    print(
        f"Model Name : {model_name}"
    )

    print(
        f"Version    : {new_version}"
    )

    print(
        f"From Alias : @{from_alias}"
    )

    print(
        f"To Alias   : @{to_alias}"
    )

    if (
        target_version
        and target_version != new_version
    ):
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

    Uses the MLflow production alias,
    not a hardcoded local file path.
    """

    model_uri = (
        f"models:/{model_name}@production"
    )

    model = mlflow.sklearn.load_model(
        model_uri
    )

    version = (
        client.get_model_version_by_alias(
            model_name,
            "production",
        ).version
    )

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
# Rollback
# ==========================================================


def rollback_model(
    model_name: str,
):
    """
    Roll Production back to the previous production version.

    Rollback deliberately bypasses the governance promotion
    gate because the target version was already live in
    Production.

    This function directly restores the production alias
    using _set_alias() and does not call promote_model().
    """

    # ------------------------------------------------------
    # Get current production version
    # ------------------------------------------------------

    current_version = (
        get_model_version_by_alias(
            model_name,
            "production",
        )
    )

    if current_version is None:
        raise RuntimeError(
            f"No production version found "
            f"for {model_name}"
        )

    current_version = str(
        current_version
    )

    # ------------------------------------------------------
    # Read current model-version metadata
    # ------------------------------------------------------

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

    # ------------------------------------------------------
    # Safety check
    # ------------------------------------------------------

    if previous_version == current_version:
        raise RuntimeError(
            "Previous production version cannot "
            "be the current production version"
        )

    # ------------------------------------------------------
    # Restore previous Production alias directly.
    #
    # IMPORTANT:
    # Do NOT call promote_model() here.
    #
    # Rollback is intentionally outside the governance
    # promotion gate because this version was already live.
    # ------------------------------------------------------

    _set_alias(
        model_name,
        "production",
        previous_version,
    )

    # ------------------------------------------------------
    # Record rollback information.
    # ------------------------------------------------------

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