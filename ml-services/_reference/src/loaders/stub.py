from typing import Any, Dict

from src.loaders.base import BaseModelLoader


class StubModel:
    """Contract-compatible model used until real artifacts are available."""

    def __init__(self, model_name: str):
        self.model_name = model_name

    def predict(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.model_name == "forecast":
            history = payload.get("history")
            horizon = payload.get("horizon", 3)

            if not isinstance(history, list) or not history:
                raise ValueError("'history' must be a non-empty list.")

            if not isinstance(horizon, int) or horizon <= 0:
                raise ValueError("'horizon' must be a positive integer.")

            last_value = float(history[-1])

            return {
                "forecast": [round(last_value, 2) for _ in range(horizon)],
                "horizon": horizon,
                "model_type": "stub",
            }

        if self.model_name == "eta":
            required = ["origin", "destination", "carrier", "weight_kg"]

            for field in required:
                if field not in payload:
                    raise ValueError(f"Missing required field: '{field}'.")

            weight = float(payload["weight_kg"])

            if weight <= 0:
                raise ValueError("'weight_kg' must be greater than 0.")

            return {
                "eta_days": 5.0,
                "confidence_low": 4.0,
                "confidence_high": 6.0,
                "model_type": "stub",
            }

        if self.model_name == "anomaly":
            required = ["temperature", "humidity", "stock_count"]

            for field in required:
                if field not in payload:
                    raise ValueError(f"Missing required field: '{field}'.")

            temperature = float(payload["temperature"])
            humidity = float(payload["humidity"])
            stock_count = float(payload["stock_count"])

            is_anomaly = (
                temperature > 80
                or humidity > 95
                or stock_count < 5
            )

            return {
                "is_anomaly": is_anomaly,
                "score": 0.85 if is_anomaly else 0.12,
                "label": "anomaly" if is_anomaly else "normal",
                "model_type": "stub",
            }

        if self.model_name == "risk":
            supplier_name = payload.get("supplier_name")
            headlines = payload.get("headlines")

            if not supplier_name:
                raise ValueError("'supplier_name' is required.")

            if not isinstance(headlines, list):
                raise ValueError("'headlines' must be a list.")

            return {
                "risk_score": 0.25,
                "confidence": 0.75,
                "risk_level": "low",
                "supplier": supplier_name,
                "model_type": "stub",
            }

        raise ValueError(f"Unsupported stub model: {self.model_name}")


class StubModelLoader(BaseModelLoader):
    """Loads a contract-compatible stub model."""

    def __init__(self, model_name: str):
        self.model_name = model_name

    def load(self) -> StubModel:
        return StubModel(self.model_name)