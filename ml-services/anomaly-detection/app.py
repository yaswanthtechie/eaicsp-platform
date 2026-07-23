from fastapi import FastAPI, HTTPException

from schemas import PredictionRequest

from src.predict import predict_with_explanation
from src.streaming import (
    start_stream,
    stop_stream,
    reset_stream,
    get_window,
    get_latest,
    get_history,
)

app = FastAPI(title="Anomaly Detection")


@app.post("/detect")
async def detect(request: PredictionRequest):
    try:
        return predict_with_explanation(
            request.reading.model_dump(),
            request.model.value,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/stream/start")
async def stream_start():
    if start_stream():
        return {"message": "Streaming started."}

    return {"message": "Streaming is already running."}


@app.post("/stream/stop")
async def stream_stop():
    stop_stream()
    return {"message": "Streaming stopped."}


@app.post("/stream/reset")
async def stream_reset():
    reset_stream()
    return {"message": "Streaming reset."}


@app.get("/stream/window/{model}")
async def stream_window(model: str):
    try:
        window = get_window(model)

        return {
            "model": model,
            "window_size": len(window),
            "window": window,
        }

    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/stream/latest/{model}")
async def stream_latest(model: str):
    try:
        result = get_latest(model)

        if result is None:
            return {"message": "Streaming has not started yet."}

        return result

    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/stream/history/{model}")
async def stream_history(model: str):
    try:
        history = get_history(model)

        return {
            "model": model,
            "total_predictions": len(history),
            "history": history,
        }

    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))