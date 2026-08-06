from collections import deque
import threading
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .model_loader import get_models
from .predict import predict

window_size = 50
history_size = 50

model_mapping = {
    "1": "iforest",
    "2": "lof",
    "3": "ocsvm",
}

# Shared state

state_lock = threading.Lock()

rolling_window = deque(maxlen=window_size)

latest_results = {
    "iforest": None,
    "lof": None,
    "ocsvm": None,
}

prediction_history = {
    "iforest": deque(maxlen=history_size),
    "lof": deque(maxlen=history_size),
    "ocsvm": deque(maxlen=history_size),
}

current_time = pd.Timestamp.now(
    tz=ZoneInfo("Asia/Kolkata")
).floor("s")

running = False
stream_thread = None

np.random.seed(42)


def generate_reading():
    """
    Generate one synthetic sensor reading.
    """

    global current_time

    reading = {
        "temperature": float(np.random.normal(22, 1.5)),
        "humidity": float(np.random.normal(45, 5)),
        "stock_count": float(np.random.normal(500, 30)),
    }

    planted = False
    anomaly_type = None

    if np.random.random() < 0.05:

        planted = True

        anomaly_type = np.random.choice(
            [
                "temperature_spike",
                "humidity_anomaly",
                "stock_anomaly",
                "combined_anomaly",
            ]
        )

        if anomaly_type == "temperature_spike":
            reading["temperature"] += float(
                np.random.uniform(8, 15)
            )

        elif anomaly_type == "humidity_anomaly":
            reading["humidity"] += float(
                np.random.uniform(20, 35)
            )

        elif anomaly_type == "stock_anomaly":
            reading["stock_count"] += float(
                np.random.uniform(150, 300)
            )

        elif anomaly_type == "combined_anomaly":
            reading["temperature"] += float(
                np.random.uniform(8, 15)
            )
            reading["humidity"] += float(
                np.random.uniform(20, 35)
            )

    with state_lock:
        timestamp = current_time
        current_time += pd.Timedelta(seconds=1)

    return timestamp, reading, planted, anomaly_type


def stream_loop():
    """
    Background streaming thread.
    """

    global running

    while True:

        with state_lock:
            if not running:
                break

        timestamp, reading, planted, anomaly_type = generate_reading()

        with state_lock:

            rolling_window.append(
                {
                    "timestamp": timestamp.isoformat(),
                    **reading,
                    "planted_anomaly": planted,
                    "anomaly_type": anomaly_type,
                }
            )

        for model in latest_results:

            result = predict(
                reading,
                model,
            )

            prediction = {
                "timestamp": timestamp.isoformat(),
                "planted_anomaly": planted,
                "anomaly_type": anomaly_type,
                "reading": reading,
                **result,
            }

            with state_lock:

                latest_results[model] = prediction

                prediction_history[model].append(
                    prediction
                )

        time.sleep(1)


def start_stream():
    """
    Start background streaming.
    """

    global running
    global stream_thread

    with state_lock:

        if running:
            return False

        get_models()

        running = True

        stream_thread = threading.Thread(
            target=stream_loop,
            daemon=True,
        )

        stream_thread.start()

    return True


def stop_stream():
    """
    Stop background streaming.
    """

    global running

    with state_lock:
        running = False


def reset_stream():
    """
    Reset all streaming state.
    """

    global current_time

    stop_stream()

    with state_lock:

        current_time = pd.Timestamp.now(
            tz=ZoneInfo("Asia/Kolkata")
        ).floor("s")

        rolling_window.clear()

        for history in prediction_history.values():
            history.clear()

        for model in latest_results:
            latest_results[model] = None


def get_window():
    """
    Return the current rolling window.
    """

    with state_lock:
        return list(rolling_window)


def get_latest(model):
    """
    Return the latest prediction.
    """

    model = model_mapping.get(
        model,
        model,
    )

    with state_lock:

        if model not in latest_results:
            raise ValueError(
                "Invalid model."
            )

        return latest_results[model]


def get_history(model):
    """
    Return prediction history.
    """

    model = model_mapping.get(
        model,
        model,
    )

    with state_lock:

        if model not in prediction_history:
            raise ValueError(
                "Invalid model."
            )

        return list(
            prediction_history[model]
        )