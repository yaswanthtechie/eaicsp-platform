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


class FeatureBuildRequest(BaseModel):
    data: list[dict[str, Any]]
    date_col: str
    target_col: str
    config: dict[str, Any] | None = Field(default=None)
    feature_version: str = "v1"


@app.post("/features/build")
def build_features(request: FeatureBuildRequest):
    """
    Build engineered features from raw input data and configuration.
    Reuse cached features when the same feature definition and data
    have already been computed.
    """

    try:
        df = pd.DataFrame(request.data)

        if not pd.api.types.is_numeric_dtype(df[request.target_col]):
            raise ValueError(
                f"Target column '{request.target_col}' must contain numeric values."
            )

        features = feature_store.get_or_compute(
            df=df,
            date_col=request.date_col,
            target_col=request.target_col,
            config=request.config,
            feature_version=request.feature_version,
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