import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .errors import InvalidPredictionRequest, LocationNotFound
from .predict import predict


logger = logging.getLogger(__name__)


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


def _error(status_code, error_code, message):
    """Every error uses the documented contract: {"error_code", "message"}."""
    return JSONResponse(
        status_code=status_code,
        content={"error_code": error_code, "message": message},
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error(request: Request, exc: RequestValidationError):
    """
    Missing fields, negative weight, empty city: rejected by Pydantic
    before predict_eta runs. Return the same contract shape as every
    other error instead of FastAPI's default {"detail": [...]}.
    """
    problems = "; ".join(
        f"{'.'.join(str(part) for part in error['loc'][1:])}: {error['msg']}"
        for error in exc.errors()
    )
    return _error(422, "INVALID_REQUEST", problems)


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
        return predict(request.model_dump())

    # ---- caller's mistake: 422 ---------------------------------------
    except LocationNotFound as exc:
        return _error(422, "LOCATION_NOT_FOUND", str(exc))

    except InvalidPredictionRequest as exc:
        return _error(422, "INVALID_REQUEST", str(exc))

    # ---- our problem: 500, details only in the server log --------------
    except (FileNotFoundError, TypeError):
        logger.exception("ETA model or data files are missing or invalid")
        return _error(
            500,
            "MODEL_CONFIGURATION_ERROR",
            "The ETA service is misconfigured. See server logs.",
        )

    except Exception:
        # Includes any other ValueError: bad calibration, a geolocation
        # file with missing columns, invalid coordinates in OUR data.
        logger.exception("ETA prediction failed")
        return _error(
            500,
            "INTERNAL_PREDICTION_ERROR",
            "Internal prediction error",
        )