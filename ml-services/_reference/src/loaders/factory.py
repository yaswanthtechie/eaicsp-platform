from src.loaders.base import BaseModelLoader
from src.loaders.stub import StubModelLoader
from src.config import MODEL_BACKEND


def create_model_loader(model_name: str) -> BaseModelLoader:
    backend = MODEL_BACKEND.strip().lower()

    if backend == "stub":
        return StubModelLoader(model_name)

    raise ValueError(
        f"Unsupported MODEL_BACKEND: '{MODEL_BACKEND}'. "
        "Supported backends: stub"
    )