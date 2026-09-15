from typing import Dict, List


MODEL_REGISTRY: Dict[str, Dict[str, str]] = {
    "forecast": {
        "model_name": "forecast",
        "production_version": "v1",
        "previous_production_version": "",
        "status": "ready",
    },
    "eta": {
        "model_name": "eta",
        "production_version": "v1",
        "previous_production_version": "",
        "status": "ready",
    },
    "anomaly": {
        "model_name": "anomaly",
        "production_version": "v1",
        "previous_production_version": "",
        "status": "ready",
    },
    "risk": {
        "model_name": "risk",
        "production_version": "v1",
        "previous_production_version": "",
        "status": "ready",
    },
}


def get_model(model_name: str) -> Dict[str, str]:
    """Return registry information for one model."""

    model_name = model_name.strip().lower()

    if model_name not in MODEL_REGISTRY:
        raise KeyError(
            f"Model '{model_name}' is not registered."
        )

    return MODEL_REGISTRY[model_name]


def list_models() -> List[Dict[str, str]]:
    """Return all registered models."""

    return list(MODEL_REGISTRY.values())


def model_exists(model_name: str) -> bool:
    """Return whether a model exists in the registry."""

    return (
        model_name.strip().lower()
        in MODEL_REGISTRY
    )


def get_production_version(model_name: str) -> str:
    """Return the current production version."""

    return get_model(model_name)[
        "production_version"
    ]


def promote_model(
    model_name: str,
    candidate_version: str,
) -> Dict[str, str]:
    """
    Promote a candidate version to production.

    The previous production version is retained so that
    the service can safely roll back.
    """

    model = get_model(model_name)

    candidate_version = candidate_version.strip()

    if not candidate_version:
        raise ValueError(
            "candidate_version cannot be empty."
        )

    previous_version = model[
        "production_version"
    ]

    if candidate_version == previous_version:
        raise ValueError(
            "Candidate version is already in production."
        )

    model[
        "previous_production_version"
    ] = previous_version

    model[
        "production_version"
    ] = candidate_version

    model["status"] = "ready"

    return dict(model)


def rollback_model(
    model_name: str,
) -> Dict[str, str]:
    """
    Roll back to the previous production version.

    Raises an error when no previous version exists.
    """

    model = get_model(model_name)

    previous_version = model.get(
        "previous_production_version",
        "",
    )

    if not previous_version:
        raise RuntimeError(
            f"No previous production version "
            f"available for '{model_name}'."
        )

    current_version = model[
        "production_version"
    ]

    model[
        "production_version"
    ] = previous_version

    model[
        "previous_production_version"
    ] = current_version

    model["status"] = "ready"

    return dict(model)