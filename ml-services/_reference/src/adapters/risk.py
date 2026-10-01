from typing import Any, Dict

from src.adapters.base import BaseModelAdapter
from src.loaders.factory import create_model_loader


class RiskAdapter(BaseModelAdapter):
    model_name = "risk"
    model_version = "v1"

    def __init__(self):
        self.model = create_model_loader(self.model_name).load()

    def predict(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.model.predict(payload)