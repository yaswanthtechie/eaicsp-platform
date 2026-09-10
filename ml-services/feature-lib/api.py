from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.build_features import build_all_features


app = FastAPI(
    title="Feature Engineering API",
    description="API for building engineered ML features.",
    version="1.0.0",
)


class FeatureBuildRequest(BaseModel):
    data: list[dict[str, Any]]
    date_col: str
    target_col: str
    config: dict[str, Any] | None = Field(default=None)


@app.post("/features/build")
def build_features(request: FeatureBuildRequest):
    """
    Build engineered features from raw input data and configuration.
    """

    try:
        df = pd.DataFrame(request.data)

        features = build_all_features(
            df=df,
            date_col=request.date_col,
            target_col=request.target_col,
            config=request.config,
        )

        safe_features = features.astype(object).where(
            pd.notna(features),
            None
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