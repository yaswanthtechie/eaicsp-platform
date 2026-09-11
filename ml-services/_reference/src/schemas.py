from typing import Any, Dict
from pydantic import BaseModel, Field


class ModelPredictionRequest(BaseModel):
    payload: Dict[str, Any] = Field(
        ...,
        description="Model-specific prediction input",
    )

    request_id: str | None = Field(
        default=None,
        description="Optional deterministic request ID for A/B assignment",
    )


class ModelPredictionResponse(BaseModel):
    model: str
    model_version: str
    prediction: Dict[str, Any]
    confidence: float | None = None
    latency_ms: float
    request_id: str | None = None
    variant: str | None = None


class ModelInfoResponse(BaseModel):
    model: str
    production_version: str
    status: str


class ModelsResponse(BaseModel):
    models: list[ModelInfoResponse]


class HealthResponse(BaseModel):
    status: str
    models: Dict[str, Dict[str, Any]]