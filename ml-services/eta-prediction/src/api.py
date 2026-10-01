
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .predict import predict


app = FastAPI(
    title="ETA Prediction Service",
    description="ETA prediction API for logistics",
    version="1.0.0",
)


class ETAPredictionRequest(BaseModel):
    origin: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)
    carrier: str = Field(..., min_length=1)
    weight_kg: float = Field(..., ge=0)


class ETAPredictionResponse(BaseModel):
    eta_days: float
    confidence_low: float
    confidence_high: float


class ErrorResponse(BaseModel):
    error_code: str
    message: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(
    "/predict",
    response_model=ETAPredictionResponse,
    responses={
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def predict_eta(request: ETAPredictionRequest):
    try:
        result = predict(request.model_dump())
        return result

    except ValueError as exc:
        message = str(exc)

        if "City not found in geolocation dataset" in message:
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "LOCATION_NOT_FOUND",
                    "message": message,
                },
            ) from exc

        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "INVALID_REQUEST",
                "message": message,
            },
        ) from exc

    except (FileNotFoundError, TypeError) as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "MODEL_CONFIGURATION_ERROR",
                "message": str(exc),
            },
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "INTERNAL_PREDICTION_ERROR",
                "message": "Internal prediction error",
            },
        ) from exc

