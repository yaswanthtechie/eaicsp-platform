from fastapi import FastAPI, HTTPException

from schemas import PredictionRequest

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
        result = predict_with_explanation(
            request.reading.model_dump(),
            request.model.value,
        )

        result["model_version"] = get_model_version()

        return result

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.post("/stream/start")
async def stream_start():
    try:
        if start_stream():
            return {"message": "Streaming started."}

        return {"message": "Streaming is already running."}

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )


@app.post("/stream/stop")
async def stream_stop():
    stop_stream()
    return {"message": "Streaming stopped."}


@app.post("/stream/reset")
async def stream_reset():
    reset_stream()
    return {"message": "Streaming reset."}


@app.get("/stream/rolling-window")
async def stream_rolling_window():
    try:
        window = get_window()

        return {
            "window_size": len(window),
            "window": window,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
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

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@app.get("/stream/detect-window/{model}")
async def stream_detect_window(model: str):
    try:
        history = get_history(model)

        return {
            "model": model,
            "window_size": len(history),
            "predictions": history,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )