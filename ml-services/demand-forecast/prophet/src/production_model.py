"""Load and invoke the registered MLflow Production forecast model."""

import os

import mlflow
import pandas as pd
from mlflow.tracking import MlflowClient


class ProductionForecastModel:
    """Strict MLflow registry adapter; never falls back to local artifacts."""

    def __init__(self):
        self.tracking_uri = os.getenv(
            "MLFLOW_TRACKING_URI",
            "http://localhost:5000",
        )
        self.model_name = os.getenv("MLFLOW_MODEL_NAME", "").strip()
        self.stage = os.getenv("MLFLOW_MODEL_STAGE", "Production")
        self.model = None
        self.model_version = None

    @property
    def is_loaded(self) -> bool:
        return self.model is not None and self.model_version is not None

    def load(self):
        """Load the latest registered model assigned to the configured stage."""
        if not self.model_name:
            raise RuntimeError(
                "MLFLOW_MODEL_NAME must identify Uday's registered forecast model."
            )

        mlflow.set_tracking_uri(self.tracking_uri)
        client = MlflowClient(tracking_uri=self.tracking_uri)

        versions = client.get_latest_versions(
            self.model_name,
            stages=[self.stage],
        )
        if not versions:
            raise RuntimeError(
                f"No registered model version found for "
                f"{self.model_name!r} in stage {self.stage!r}."
            )

        selected = max(versions, key=lambda item: int(item.version))
        model_uri = f"models:/{self.model_name}/{selected.version}"

        # Only mark the model loaded after MLflow successfully loads it.
        loaded_model = mlflow.pyfunc.load_model(model_uri)
        self.model = loaded_model
        self.model_version = str(selected.version)
        return self

    def predict(self, sku_id: str, warehouse_id: str, horizon: int) -> list[dict]:
        """Request a forecast and enforce the A2 daily-point contract."""
        if not self.is_loaded:
            raise RuntimeError("Forecast Production model is not loaded.")

        model_input = pd.DataFrame([{
            "sku_id": sku_id,
            "warehouse_id": warehouse_id,
            "horizon": horizon,
        }])
        result = self.model.predict(model_input)

        if isinstance(result, pd.DataFrame):
            points = result.to_dict(orient="records")
        elif isinstance(result, dict):
            points = result.get("forecast")
        elif isinstance(result, list):
            points = result
        else:
            raise ValueError(
                "MLflow pyfunc output must be a DataFrame, list, "
                "or a dictionary containing 'forecast'."
            )

        if not isinstance(points, list) or len(points) != horizon:
            raise ValueError(
                f"MLflow model must return exactly {horizon} daily forecast points."
            )

        required = {"date", "predicted", "lower_bound", "upper_bound"}
        normalized = []
        previous_date = None

        for point in points:
            if not isinstance(point, dict) or not required.issubset(point):
                raise ValueError(
                    "Each forecast point must contain date, predicted, "
                    "lower_bound, and upper_bound."
                )

            date = pd.Timestamp(point["date"]).date()
            predicted = float(point["predicted"])
            lower = float(point["lower_bound"])
            upper = float(point["upper_bound"])

            if not all(pd.notna(value) for value in (predicted, lower, upper)):
                raise ValueError("Forecast values must be finite numbers.")
            if not all(abs(value) != float("inf") for value in (predicted, lower, upper)):
                raise ValueError("Forecast values must be finite numbers.")
            if lower < 0 or predicted < 0 or upper < 0:
                raise ValueError("Forecast values cannot be negative.")
            if not lower <= predicted <= upper:
                raise ValueError("Forecast bounds must satisfy lower_bound <= predicted <= upper_bound.")
            if previous_date is not None and (date - previous_date).days != 1:
                raise ValueError("Forecast dates must be consecutive and ascending.")

            normalized.append({
                "date": date.isoformat(),
                "predicted": predicted,
                "lower_bound": lower,
                "upper_bound": upper,
            })
            previous_date = date

        return normalized
