"""Load and invoke the registered MLflow production forecast model."""

import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from threading import RLock

import mlflow
import pandas as pd
from mlflow.tracking import MlflowClient

logger = logging.getLogger(__name__)


class ProductionForecastModel:
    """MLflow registry adapter with a persistent last-known-good model cache."""

    def __init__(self):
        self.tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "").strip()
        self.model_name = os.getenv("MLFLOW_MODEL_NAME", "").strip()
        self.model_alias = os.getenv("MLFLOW_MODEL_ALIAS", "production").strip()

        configured_cache = os.getenv("MLFLOW_MODEL_CACHE_DIR", "./model_cache")
        self.cache_dir = Path(configured_cache).expanduser().resolve()
        self.cache_metadata = self.cache_dir / "latest.json"

        self.model = None
        self.model_version = None
        self.load_status = "unhealthy"
        self.load_error = None
        self._lock = RLock()

    @property
    def is_loaded(self) -> bool:
        return self.model is not None and self.model_version is not None

    @property
    def model_name_value(self) -> str | None:
        return self.model_name or None

    def _validate_config(self) -> None:
        if not self.tracking_uri:
            raise RuntimeError(
                "MLFLOW_TRACKING_URI is required; configure the MLflow tracking server URL."
            )
        if not self.model_name:
            raise RuntimeError("MLFLOW_MODEL_NAME must identify the registered forecast model.")
        if not self.model_alias:
            raise RuntimeError("MLFLOW_MODEL_ALIAS must identify the production alias.")

    def _save_cache(self, loaded_model, version: str, model_path: Path) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        metadata = {
            "model_name": self.model_name,
            "model_alias": self.model_alias,
            "model_version": version,
            "model_path": str(model_path.relative_to(self.cache_dir)),
        }

        temporary_metadata = self.cache_metadata.with_suffix(".tmp")
        temporary_metadata.write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )
        temporary_metadata.replace(self.cache_metadata)

    def _download_and_cache(self, model_uri: str, version: str):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        target_dir = self.cache_dir / self.model_name / version
        target_dir.parent.mkdir(parents=True, exist_ok=True)

        temporary_root = Path(
            tempfile.mkdtemp(prefix="mlflow-download-", dir=self.cache_dir)
        )

        try:
            downloaded_path = Path(
                mlflow.artifacts.download_artifacts(
                    artifact_uri=model_uri,
                    dst_path=str(temporary_root / "artifact"),
                )
            )

            if target_dir.is_dir():
                # Registry versions are immutable; reuse an existing version cache.
                loaded_model = mlflow.pyfunc.load_model(str(target_dir))
            else:
                replacement_dir = target_dir.with_name(target_dir.name + ".new")
                if replacement_dir.exists():
                    shutil.rmtree(replacement_dir)

                shutil.move(str(downloaded_path), str(replacement_dir))
                replacement_dir.replace(target_dir)

                try:
                    # Load from the permanent path, not the temporary download path.
                    loaded_model = mlflow.pyfunc.load_model(str(target_dir))
                except Exception:
                    shutil.rmtree(target_dir, ignore_errors=True)
                    raise

            self._save_cache(loaded_model, version, target_dir)
            return loaded_model

        finally:
            shutil.rmtree(temporary_root, ignore_errors=True)

    def _load_cache(self):
        if not self.cache_metadata.is_file():
            raise RuntimeError("No cached production forecast model is available.")

        metadata = json.loads(self.cache_metadata.read_text(encoding="utf-8"))

        if metadata.get("model_name") != self.model_name:
            raise RuntimeError("Cached model belongs to a different registry model.")

        relative_path = Path(metadata["model_path"])
        model_path = (self.cache_dir / relative_path).resolve()

        # Prevent cache metadata from loading paths outside the configured cache.
        if not model_path.is_relative_to(self.cache_dir):
            raise RuntimeError("Cached model path is outside the configured cache directory.")

        if not model_path.is_dir():
            raise RuntimeError("Cached production model artifacts are missing.")

        loaded_model = mlflow.pyfunc.load_model(str(model_path))
        return loaded_model, str(metadata["model_version"])

    def load(self):
        """Load the production alias, or use the last-known-good local cache."""
        self._validate_config()

        with self._lock:
            try:
                mlflow.set_tracking_uri(self.tracking_uri)
                client = MlflowClient(tracking_uri=self.tracking_uri)

                # Resolve the production alias to a concrete registry version.
                selected = client.get_model_version_by_alias(
                    self.model_name,
                    self.model_alias,
                )
                version = str(selected.version)
                model_uri = f"models:/{self.model_name}/{version}"

                loaded_model = self._download_and_cache(model_uri, version)

                self.model = loaded_model
                self.model_version = version
                self.load_status = "ready"
                self.load_error = None

                logger.info(
                    "Loaded MLflow model %s version %s through alias %s",
                    self.model_name,
                    version,
                    self.model_alias,
                )
                return self

            except Exception as exc:
                self.load_error = str(exc)
                logger.warning(
                    "Unable to load MLflow production alias %s for %s: %s",
                    self.model_alias,
                    self.model_name,
                    exc,
                )

                # Never discard a working in-memory model on a failed reload.
                if self.is_loaded:
                    self.load_status = "degraded"
                    return self

                try:
                    cached_model, cached_version = self._load_cache()
                    self.model = cached_model
                    self.model_version = cached_version
                    self.load_status = "degraded"

                    logger.warning(
                        "Using cached MLflow model %s version %s; registry is unavailable.",
                        self.model_name,
                        cached_version,
                    )
                    return self

                except Exception as cache_exc:
                    self.load_status = "unhealthy"
                    logger.exception(
                        "MLflow is unavailable and no usable cached model exists."
                    )
                    raise RuntimeError(
                        "Could not load the production forecast model from MLflow "
                        "or the local cache. "
                        f"Registry error: {exc}. Cache error: {cache_exc}"
                    ) from exc

    def predict(self, sku_id: str, warehouse_id: str, horizon: int) -> list[dict]:
        """Request a forecast and enforce the A2 daily-point contract."""
        with self._lock:
            if not self.is_loaded:
                raise RuntimeError("Forecast production model is not loaded.")

            model = self.model

        model_input = pd.DataFrame([{
            "sku_id": sku_id,
            "warehouse_id": warehouse_id,
            "horizon": horizon,
        }])
        model_input["sku_id"] = model_input["sku_id"].astype("string")
        model_input["warehouse_id"] = model_input["warehouse_id"].astype("string")
        model_input["horizon"] = model_input["horizon"].astype("int64")

        result = model.predict(model_input)

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
                raise ValueError(
                    "Forecast bounds must satisfy lower_bound <= predicted <= upper_bound."
                )
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
