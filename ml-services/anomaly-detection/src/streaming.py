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

rolling_windows = {
    "iforest": deque(maxlen=window_size),
    "lof": deque(maxlen=window_size),
    "ocsvm": deque(maxlen=window_size),
}

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

current_time = pd.Timestamp.now(tz=ZoneInfo("Asia/Kolkata")).floor("s")

running = False
stream_thread = None

np.random.seed(42)


def generate_reading():
    global current_time

    reading = {
        "temperature": float(np.random.normal(22, 1.5)),
        "humidity": float(np.random.normal(45, 5)),
        "stock_count": float(np.random.normal(500, 30)),
    }

    planted = False

    # Random temperature anomaly with 5% probability
    if np.random.random() < 0.05:
        reading["temperature"] += float(np.random.uniform(8, 15))
        planted = True

    timestamp = current_time
    current_time += pd.Timedelta(seconds=1)

    return timestamp, reading, planted


def stream_loop():
    global running

    while running:

        timestamp, reading, planted = generate_reading()

        for model in rolling_windows:

            rolling_windows[model].append(
                {
                    "timestamp": timestamp.isoformat(),
                    **reading,
                    "planted_anomaly": planted,
                }
            )

            result = predict(reading, model)

            prediction = {
                "timestamp": timestamp.isoformat(),
                "planted_anomaly": planted,
                "reading": reading,
                **result,
            }

            latest_results[model] = prediction

            prediction_history[model].append(prediction)

        time.sleep(1)


def start_stream():
    global running, stream_thread

    if running:
        return False

    # Ensure trained models exist before starting the stream.
    # Raises FileNotFoundError if models are missing.
    get_models()

    running = True

    stream_thread = threading.Thread(
        target=stream_loop,
        daemon=True,
    )

    stream_thread.start()

    return True


def stop_stream():
    global running

    running = False


def reset_stream():
    global current_time

    stop_stream()

    current_time = pd.Timestamp.now(tz=ZoneInfo("Asia/Kolkata")).floor("s")

    for window in rolling_windows.values():
        window.clear()

    for history in prediction_history.values():
        history.clear()

    for model in latest_results:
        latest_results[model] = None


def get_window(model):
    model = model_mapping.get(model, model)

    if model not in rolling_windows:
        raise ValueError("Invalid model.")

    return list(rolling_windows[model])


def get_latest(model):
    model = model_mapping.get(model, model)

    if model not in latest_results:
        raise ValueError("Invalid model.")

    return latest_results[model]


def get_history(model):
    model = model_mapping.get(model, model)

    if model not in prediction_history:
        raise ValueError("Invalid model.")

    return list(prediction_history[model])