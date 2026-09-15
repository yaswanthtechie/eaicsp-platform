import logging

from fastapi import FastAPI, HTTPException

from schemas import (
    DetectAdaptiveRequest,
    DetectWindowRequest,
    PredictionRequest,
)

from src.model_loader import (
    get_model_version,
)

from src.predict import (
    adaptive_engine_predict_with_explanation,
    predict_with_explanation,
)

from src.streaming import (
    get_history,
    get_latest,
    get_window,
    reset_stream,
    start_stream,
    stop_stream,
)


logger = logging.getLogger(__name__)

app = FastAPI(
    title="Anomaly Detection"
)


# ============================================================
# HELPERS
# ============================================================

def sensor_features(reading):
    """
    Extract only the features required by the ML models.

    reading_id is an identifier used by the streaming /
    deduplication layer and must NOT be treated as an ML feature.
    """

    return {
        "temperature": reading.temperature,
        "humidity": reading.humidity,
        "stock_count": reading.stock_count,
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "anomaly-detection-api",
        "model_version": get_model_version(),
    }


# ============================================================
# SINGLE READING DETECTION
# ============================================================

@app.post("/detect")
async def detect(
    request: PredictionRequest,
):
    """
    Detect an anomaly for a single sensor reading
    using the model's native prediction.

    This endpoint intentionally does NOT use the
    adaptive state machine.
    """

    try:

        features = sensor_features(
            request.reading
        )

        return predict_with_explanation(
            features,
            request.model.value,
        )

    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception:

        logger.exception(
            "Unexpected error while processing "
            "/detect request."
        )

        raise HTTPException(
            status_code=500,
            detail="Internal server error.",
        )


# ============================================================
# ROLLING WINDOW DETECTION
# ============================================================

@app.post("/detect-window")
async def detect_window(
    request: DetectWindowRequest,
):
    """
    Detect anomalies over the supplied sensor readings
    using the model's native prediction.

    This endpoint intentionally does NOT use the
    adaptive state machine.
    """

    try:

        anomalous_readings = []

        for window_index, reading in enumerate(
            request.readings
        ):

            features = sensor_features(
                reading
            )

            result = predict_with_explanation(
                features,
                request.model.value,
            )

            if result["is_anomaly"]:

                anomalous_readings.append(
                    {
                        "reading_id": (
                            reading.reading_id
                        ),
                        "reading_index": (
                            window_index
                        ),
                        "is_anomaly": (
                            result["is_anomaly"]
                        ),
                        "score": (
                            result["score"]
                        ),
                        "reasons": (
                            result["reasons"]
                        ),
                    }
                )

        return {
            "model": request.model.value,
            "model_version": (
                get_model_version()
            ),
            "window_size": len(
                request.readings
            ),
            "total_anomalies": len(
                anomalous_readings
            ),
            "anomalous_readings": (
                anomalous_readings
            ),
        }

    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception:

        logger.exception(
            "Unexpected error while processing "
            "/detect-window request."
        )

        raise HTTPException(
            status_code=500,
            detail="Internal server error.",
        )


# ============================================================
# ADAPTIVE DETECTION
# ============================================================

@app.post("/detect-adaptive")
async def detect_adaptive(
    request: DetectAdaptiveRequest,
):
    """
    Stateful adaptive anomaly detection.

    Architecture:

        SENSOR READINGS
              |
              v
        SEQUENTIAL PROCESSING
              |
              v
        MODEL PREDICTION
              |
              v
          MODEL SCORE
              |
              v
        REGIME DETECTOR
              |
        +-----+------+
        |            |
    NO CHANGE      CHANGE
        |            |
        v            v
    PREVIOUS      TEMPORAL
    THRESHOLD      CHECK
                     |
                +----+----+
                |         |
              DRIFT     NO DRIFT
                |         |
                v         v
              ALERT    REGIME
               ONLY    CONFIRMATION
                         |
                         v
                     ADAPTATION

    The AdaptiveEngine owns the complete lifecycle.

    This endpoint accepts either one reading or multiple
    readings and processes every reading sequentially through
    the same stateful AdaptiveEngine.

    State is maintained by AdaptiveEngineManager,
    with one engine per model.
    """

    try:

        # ----------------------------------------------------
        # SINGLE READING
        # ----------------------------------------------------

        if request.reading is not None:

            features = sensor_features(
                request.reading
            )

            return (
                adaptive_engine_predict_with_explanation(
                    features,
                    request.model.value,
                )
            )

        # ----------------------------------------------------
        # MULTIPLE READINGS
        # ----------------------------------------------------

        adaptive_results = []

        anomalous_readings = []

        for reading_index, reading in enumerate(
            request.readings
        ):

            features = sensor_features(
                reading
            )

            result = (
                adaptive_engine_predict_with_explanation(
                    features,
                    request.model.value,
                )
            )

            adaptive_result = {
                "reading_id": (
                    reading.reading_id
                ),
                "reading_index": (
                    reading_index
                ),
                "is_anomaly": bool(
                    result.get(
                        "is_anomaly",
                        False,
                    )
                ),
                "score": result.get(
                    "score"
                ),
                "adaptive_threshold": (
                    result.get(
                        "adaptive_threshold"
                    )
                ),
                "state": result.get(
                    "state"
                ),
                "regime_changed": bool(
                    result.get(
                        "regime_changed",
                        False,
                    )
                ),
                "regime_confirmed": bool(
                    result.get(
                        "regime_confirmed",
                        False,
                    )
                ),
                "temporal_drift": bool(
                    result.get(
                        "temporal_drift",
                        False,
                    )
                ),
                "adapted": bool(
                    result.get(
                        "adapted",
                        False,
                    )
                ),
                "alert": bool(
                    result.get(
                        "alert",
                        False,
                    )
                ),
                "reasons": result.get(
                    "reasons",
                    [],
                ),
            }

            adaptive_results.append(
                adaptive_result
            )

            if adaptive_result[
                "is_anomaly"
            ]:

                anomalous_readings.append(
                    adaptive_result
                )

        return {
            "model": request.model.value,
            "model_version": (
                get_model_version()
            ),
            "window_size": len(
                request.readings
            ),
            "processed_readings": len(
                request.readings
            ),
            "total_anomalies": len(
                anomalous_readings
            ),
            "anomalous_readings": (
                anomalous_readings
            ),
            "adaptive_results": (
                adaptive_results
            ),
        }

    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception:

        logger.exception(
            "Unexpected error while processing "
            "/detect-adaptive request."
        )

        raise HTTPException(
            status_code=500,
            detail="Internal server error.",
        )


# ============================================================
# BACKGROUND STREAMING
# ============================================================

@app.post("/stream/start")
async def stream_start():

    try:

        if start_stream():

            return {
                "message": "Streaming started."
            }

        return {
            "message": (
                "Streaming is already running."
            )
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


# ============================================================
# ROLLING WINDOW
# ============================================================

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
            "Unexpected error while retrieving "
            "rolling window."
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "Unable to retrieve rolling window."
            ),
        )


# ============================================================
# LATEST PREDICTION
# ============================================================

@app.get("/stream/latest/{model}")
async def stream_latest(
    model: str,
):

    try:

        result = get_latest(
            model
        )

        if result is None:

            return {
                "message": (
                    "Streaming has not started yet."
                )
            }

        return result

    except Exception:

        logger.exception(
            "Unexpected error while retrieving "
            "latest prediction."
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "Unable to retrieve latest prediction."
            ),
        )


# ============================================================
# PREDICTION HISTORY
# ============================================================

@app.get(
    "/stream/prediction-history/{model}"
)
async def stream_prediction_history(
    model: str,
):

    try:

        history = get_history(
            model
        )

        return {
            "model": model,
            "window_size": len(history),
            "predictions": history,
        }

    except Exception:

        logger.exception(
            "Unexpected error while retrieving "
            "prediction history."
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "Unable to retrieve prediction history."
            ),
        )