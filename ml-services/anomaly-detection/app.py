import logging

from fastapi import FastAPI, HTTPException

from schemas import (
    DetectWindowRequest,
    PredictionRequest,
)

from src.model_loader import get_model_version
from src.predict import predict_with_explanation
from src.streaming import (
    get_history,
    get_latest,
    get_window,
    reset_stream,
    start_stream,
    stop_stream,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Anomaly Detection")


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "anomaly-detection-api",
        "model_version": get_model_version(),
    }


@app.post("/detect")
async def detect(request: PredictionRequest):
    try:
        return predict_with_explanation(
            request.reading.model_dump(),
            request.model.value,
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )

    except Exception:
        logger.exception(
            "Unexpected error while processing /detect request."
        )

        raise HTTPException(
            status_code=500,
            detail="Internal server error.",
        )


@app.post("/detect-window")
async def detect_window(request: DetectWindowRequest):
    """
    Detect anomalies over a client-provided rolling window.

    The client sends the latest N sensor readings.
    The API returns only the anomalous readings
    within that window.
    """

    try:

        anomalous_readings = []

        for index, reading in enumerate(request.readings):

            result = predict_with_explanation(
                reading.model_dump(),
                request.model.value,
            )

            if result["is_anomaly"]:

                anomalous_readings.append(
                    {
                        "reading_index": index,
                        "is_anomaly": result["is_anomaly"],
                        "score": result["score"],
                        "reasons": result["reasons"],
                    }
                )

        return {
            "model": request.model.value,
            "model_version": get_model_version(),
            "window_size": len(request.readings),
            "total_anomalies": len(anomalous_readings),
            "anomalous_readings": anomalous_readings,
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )

    except Exception:
        logger.exception(
            "Unexpected error while processing /detect-window request."
        )

        raise HTTPException(
            status_code=500,
            detail="Internal server error.",
        )


@app.post("/stream/start")
async def stream_start():
    try:

        if start_stream():
            return {
                "message": "Streaming started."
            }

        return {
            "message": "Streaming is already running."
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )


@app.post("/stream/stop")
async def stream_stop():
    stop_stream()

    return {
        "message": "Streaming stopped."
    }


@app.post("/stream/reset")
async def stream_reset():
    reset_stream()

    return {
        "message": "Streaming reset."
    }


@app.get("/stream/rolling-window")
async def stream_rolling_window():
    try:

        window = get_window()

        return {
            "window_size": len(window),
            "window": window,
        }

    except Exception:
        logger.exception(
            "Unexpected error while retrieving rolling window."
        )

        raise HTTPException(
            status_code=400,
            detail="Unable to retrieve rolling window.",
        )


@app.get("/stream/latest/{model}")
async def stream_latest(model: str):
    try:

        result = get_latest(model)

        if result is None:
            return {
                "message": "Streaming has not started yet."
            }

        return result

    except Exception:
        logger.exception(
            "Unexpected error while retrieving latest prediction."
        )

        raise HTTPException(
            status_code=400,
            detail="Unable to retrieve latest prediction.",
        )


@app.get("/stream/prediction-history/{model}")
async def stream_prediction_history(model: str):
    try:

        history = get_history(model)

        return {
            "model": model,
            "window_size": len(history),
            "predictions": history,
        }

    except Exception:
        logger.exception(
            "Unexpected error while retrieving prediction history."
        )

        raise HTTPException(
            status_code=400,
            detail="Unable to retrieve prediction history.",
        )