from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.feature_store import FeatureStore


app = FastAPI(
    title="Feature Engineering API",
    description="API for building engineered ML features.",
    version="1.0.0",
)


feature_store = FeatureStore()

MAX_ROWS = 100_000
MAX_LAG = 365
MAX_WINDOW = 365


class FeatureBuildRequest(BaseModel):
    data: list[dict[str, Any]] = Field(..., max_length=MAX_ROWS)
    date_col: str
    target_col: str
    config: dict[str, Any] | None = Field(default=None)
    feature_version: str = "v1"
    group_cols: list[str] | None = None


@app.post("/features/build")

def build_features(request: FeatureBuildRequest):
    """
    Build engineered features from raw input data and configuration.
    Reuse cached features when the same feature definition and data
    have already been computed.
    """

    try:
        df = pd.DataFrame(request.data)

        config = request.config or {}

        for lag in config.get("lags", []):
            if not isinstance(lag, int) or isinstance(lag, bool) or lag <= 0:
                raise ValueError("Lag values must be positive integers.")

            if lag > MAX_LAG:
                raise ValueError(
                    f"Lag value {lag} exceeds the maximum allowed value of "
                    f"{MAX_LAG}."
                )

        for window in config.get("windows", []):
            if (
                not isinstance(window, int)
                or isinstance(window, bool)
                or window <= 0
            ):
                raise ValueError("Window values must be positive integers.")

            if window > MAX_WINDOW:
                raise ValueError(
                    f"Window value {window} exceeds the maximum allowed value of "
                    f"{MAX_WINDOW}."
                )

        if not pd.api.types.is_numeric_dtype(df[request.target_col]):
            raise ValueError(
                f"Target column '{request.target_col}' must contain numeric values."
            )

        features = feature_store.get_or_compute(
            df=df,
            date_col=request.date_col,
            target_col=request.target_col,
            config=config,
            feature_version=request.feature_version,
            group_cols=request.group_cols,
        )

        safe_features = features.astype(object).where(
            pd.notna(features),
            None,
        )

        records = safe_features.to_dict(orient="records")

        return {
            "features": records,
        }

    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc