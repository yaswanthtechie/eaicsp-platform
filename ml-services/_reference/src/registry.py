from typing import Dict, List


MODEL_REGISTRY: Dict[str, Dict[str, str]] = {
    "forecast": {
        "model_name": "forecast",
        "production_version": "v1",
        "status": "ready",
    },
    "eta": {
        "model_name": "eta",
        "production_version": "v1",
        "status": "ready",
    },
    "anomaly": {
        "model_name": "anomaly",
        "production_version": "v1",
        "status": "ready",
    },
    "risk": {
        "model_name": "risk",
        "production_version": "v1",
        "status": "ready",
    },
}


def get_model(model_name: str) -> Dict[str, str]:
    model_name = model_name.strip().lower()

    if model_name not in MODEL_REGISTRY:
        raise KeyError(f"Model '{model_name}' is not registered.")

    return MODEL_REGISTRY[model_name]


def list_models() -> List[Dict[str, str]]:
    return list(MODEL_REGISTRY.values())


def model_exists(model_name: str) -> bool:
    return model_name.strip().lower() in MODEL_REGISTRY


def get_production_version(model_name: str) -> str:
    return get_model(model_name)["production_version"]