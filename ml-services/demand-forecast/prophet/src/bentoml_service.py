"""BentoML service for the A2 daily demand forecast contract."""

import time
from datetime import datetime, timezone

import bentoml
from fastapi import FastAPI, Header, HTTPException, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from src.errors import ContractError, register_error_handlers
from src.platform_auth import verify_platform_api_key
from src.production_model import ProductionForecastModel

RELOAD_INTERVAL_SECONDS = 30

app = FastAPI(title="Demand Forecast Serving API", version="1.0.0")
register_error_handlers(app)


class ForecastPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    predicted: float = Field(ge=0)
    lower_bound: float = Field(ge=0)
    upper_bound: float = Field(ge=0)


class ForecastResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str = "v1"
    sku_id: str
    warehouse_id: str
    granularity: str = "daily"
    horizon: int = Field(ge=1, le=90)
    interval_level: float = 0.8
    model_name: str
    model_version: str
    generated_at: datetime
    forecast: list[ForecastPoint]


@bentoml.service(name="forecast_service")
@bentoml.asgi_app(app, path="/")
class ForecastService:
    def __init__(self):
        self.production_model = ProductionForecastModel()
        self.total_predictions = 0
        self.total_latency = 0.0
        self.error_count = 0
        self.load_error = None
        self.last_load_attempt = time.monotonic()

        # Startup must fail if neither MLflow nor the local cache provides a model.
        # ProductionForecastModel.load() handles cache fallback and raises if unavailable.
        self.production_model.load()
        self.load_error = self.production_model.load_error

        app.state.forecast_service = self

    def try_load(self, force: bool = False) -> None:
        """Retry loading when no model is available, with a rate limit."""
        if self.production_model.is_loaded:
            return

        now = time.monotonic()
        if not force and now - self.last_load_attempt < RELOAD_INTERVAL_SECONDS:
            return

        self.last_load_attempt = now
        try:
            self.production_model.load()
            self.load_error = self.production_model.load_error
        except Exception as exc:
            self.load_error = str(exc)


def _model_status(service) -> str:
    model = service.production_model
    if not model.is_loaded:
        return "unhealthy"
    return getattr(model, "load_status", "ready")


@app.get("/health")
def health(request: Request) -> dict:
    service = request.app.state.forecast_service
    service.try_load()

    model = service.production_model
    status = _model_status(service)

    if not model.is_loaded:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "model_loaded": False,
                "error": service.load_error or "Production model is not loaded.",
            },
        )

    return {
        "status": status,
        "model_loaded": True,
        "model_name": getattr(model, "model_name", None) or "demand_forecast",
        "model_version": model.model_version,
    }


@app.get("/model/readyz")
def readiness(request: Request) -> dict:
    service = request.app.state.forecast_service
    service.try_load()

    if not service.production_model.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="Production model is unavailable.",
        )

    return {"status": _model_status(service)}


@app.get("/service_metrics")
def service_metrics(request: Request) -> dict:
    service = request.app.state.forecast_service
    model = service.production_model

    average_latency = (
        service.total_latency / service.total_predictions
        if service.total_predictions
        else 0.0
    )

    return {
        "model_name": getattr(model, "model_name", None) or "demand_forecast",
        "model_version": model.model_version,
        "model_status": _model_status(service),
        "model_loaded": model.is_loaded,
        "total_predictions": service.total_predictions,
        "average_latency_ms": round(average_latency, 3),
        "error_count": service.error_count,
    }


@app.post("/admin/reload-model")
def reload_model(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    # Admin reload is a service-to-service operation and must be authenticated.
    verify_platform_api_key(x_api_key)

    service = request.app.state.forecast_service

    try:
        service.production_model.load()
        service.load_error = service.production_model.load_error
    except Exception as exc:
        service.load_error = str(exc)
        raise ContractError(
            503,
            "MODEL_RELOAD_FAILED",
            "Could not load the production forecast model",
        ) from exc

    status = _model_status(service)
    if status != "ready":
        raise ContractError(
            503,
            "MODEL_RELOAD_FAILED",
            "The production alias could not be refreshed; the previous cached model may still be serving",
        )

    return {
        "status": "reloaded",
        "model_name": getattr(service.production_model, "model_name", None)
        or "demand_forecast",
        "model_version": service.production_model.model_version,
    }


@app.get("/api/v1/demand/forecast/{sku_id}", response_model=ForecastResponse)
def forecast(
    request: Request,
    sku_id: str = Path(pattern=r"^SKU-[0-9]{6}$"),
    warehouse_id: str = Query(pattern=r"^WH-[A-Z]{3}-[0-9]{2}$"),
    horizon: int = Query(default=30, ge=1, le=90),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> ForecastResponse:
    verify_platform_api_key(x_api_key)

    service = request.app.state.forecast_service
    service.try_load()

    if not service.production_model.is_loaded:
        service.error_count += 1
        raise ContractError(
            503,
            "MODEL_UNAVAILABLE",
            "Forecast model is not loaded",
        )

    start = time.perf_counter()

    try:
        points = service.production_model.predict(
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            horizon=horizon,
        )

        model = service.production_model
        response = ForecastResponse(
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            horizon=horizon,
            model_name=getattr(model, "model_name", None) or "demand_forecast",
            model_version=model.model_version,
            generated_at=datetime.now(timezone.utc),
            forecast=points,
        )

        service.total_predictions += 1
        service.total_latency += (time.perf_counter() - start) * 1000
        return response

    except HTTPException:
        raise
    except Exception as exc:
        service.error_count += 1
        raise ContractError(
            503,
            "MODEL_UNAVAILABLE",
            "Forecast generation failed",
        ) from exc
