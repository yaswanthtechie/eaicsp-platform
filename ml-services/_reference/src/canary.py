
"""
Canary / A-B model serving utilities.

R4 behavior:

    @production -> stable model
    @staging    -> canary model

Default traffic split:

    90% -> production
    10% -> staging

Routing is deterministic:
the same input features always select
the same model alias.
"""

import hashlib

import mlflow.sklearn
from mlflow.tracking import MlflowClient
from src.config import CANARY_PERCENTAGE

from src.config import MODEL_NAME


# ==========================================================
# MLflow Client
# ==========================================================

client = MlflowClient()


# ==========================================================
# Get Model Version
# ==========================================================

def get_alias_version(
    model_name: str,
    alias: str,
) -> str:
    """
    Get the model version assigned to an MLflow alias.

    Example:
        production -> "1"
        staging    -> "2"
    """

    try:
        model_version = client.get_model_version_by_alias(
            model_name,
            alias,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Unable to find alias "
            f"'{alias}' for model '{model_name}'."
        ) from exc

    if model_version is None:
        raise RuntimeError(
            f"No model version found for "
            f"{model_name}@{alias}"
        )

    return str(model_version.version)


# ==========================================================
# Load Model From Alias
# ==========================================================

def load_alias_model(
    model_name: str,
    alias: str,
):
    """
    Load a model using an MLflow alias.

    Returns:
        model, model_version
    """

    version = get_alias_version(
        model_name,
        alias,
    )

    model_uri = (
        f"models:/{model_name}@{alias}"
    )

    try:
        model = mlflow.sklearn.load_model(
            model_uri
        )
    except Exception as exc:
        raise RuntimeError(
            f"Unable to load model "
            f"{model_name}@{alias}"
        ) from exc

    return model, version


# ==========================================================
# Deterministic Hash
# ==========================================================

def deterministic_bucket(
    features: list[float],
) -> int:
    """
    Convert input features into a deterministic
    bucket from 0 to 99.

    The same feature vector always produces
    the same bucket.
    """

    normalized = ",".join(
        f"{value:.10f}"
        for value in features
    )

    digest = hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()

    return int(digest[:8], 16) % 100


# ==========================================================
# Canary Routing
# ==========================================================

def select_alias(
    features: list[float],
    canary_percentage: int = CANARY_PERCENTAGE,
) -> str:
    """
    Select production or staging deterministically.

    Default:
        90% production
        10% staging

    Example:

        bucket = 5
            -> staging

        bucket = 50
            -> production
    """

    if not isinstance(
        canary_percentage,
        int,
    ):
        raise TypeError(
            "canary_percentage must be an integer."
        )

    if not 0 <= canary_percentage <= 100:
        raise ValueError(
            "canary_percentage must be "
            "between 0 and 100."
        )

    bucket = deterministic_bucket(
        features
    )

    if bucket < canary_percentage:
        return "staging"

    return "production"


# ==========================================================
# Load Both Canary Models
# ==========================================================

def load_canary_models(
    model_name: str = MODEL_NAME,
):
    """
    Load both Production and Staging models.

    Returns:

        {
            "production": (
                production_model,
                production_version,
            ),

            "staging": (
                staging_model,
                staging_version,
            ),
        }
    """

    production_model, production_version = (
        load_alias_model(
            model_name,
            "production",
        )
    )

    staging_model, staging_version = (
        load_alias_model(
            model_name,
            "staging",
        )
    )

    return {
        "production": (
            production_model,
            production_version,
        ),
        "staging": (
            staging_model,
            staging_version,
        ),
    }


# ==========================================================
# Select Model
# ==========================================================

def select_model(
    features: list[float],
    models: dict,
    canary_percentage: int = CANARY_PERCENTAGE,
):
    """
    Select the actual model for a request.

    Returns:

        model,
        alias,
        model_version,
        bucket
    """

    alias = select_alias(
        features=features,
        canary_percentage=canary_percentage,
    )

    model, version = models[alias]

    bucket = deterministic_bucket(
        features
    )

    return (
        model,
        alias,
        version,
        bucket,
    )


# ==========================================================
# Canary Information
# ==========================================================

def get_canary_info(
    models: dict,
    canary_percentage: int = CANARY_PERCENTAGE,
) -> dict:
    """
    Return information about the active
    canary configuration.
    """

    production_model, production_version = (
        models["production"]
    )

    staging_model, staging_version = (
        models["staging"]
    )

    # Avoid unused-variable warnings while
    # keeping the model tuples explicit.
    _ = production_model
    _ = staging_model

    return {
        "model_name": MODEL_NAME,
        "traffic_split": {
            "production": 100 - canary_percentage,
            "staging": canary_percentage,
        },
        "production_version": str(
            production_version
        ),
        "staging_version": str(
            staging_version
        ),
    }

