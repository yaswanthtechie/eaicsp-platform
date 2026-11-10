"""
Warehouse sensor stream simulator.

Sensors share one normal distribution, 5-minute steps. Each sensor gets 6
injected episodes (4 multi-reading, 1 mild single reading, 1 severe single
reading) AFTER a clean warm-up. The CLI uses config/sensors.json (python -m
src.sensor_config), generated from the shared seed warehouses. SENSOR_IDS is
only the default for build_stream() in unit tests and the in-memory
evaluation.

Amplitudes and seeds are fixed design constants. They were not tuned on any
detection result. Held-out kinds (gradual_drift, flatline) are for reporting
only.
"""

import argparse
import json
import os
import time
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from .sensor_config import CONFIG_PATH, load_sensors


FEATURES = ["temperature", "humidity", "door_open", "power"]
SENSOR_IDS = ["wh1-s1", "wh1-s2", "wh1-s3"]

# Separate seeds: training, calibration and evaluation never share data.
TRAIN_SEED = 2001
CALIBRATION_SEED = 2002
STREAM_SEED = 2003

START_TIME = datetime(2026, 3, 1, tzinfo=UTC)
STEP = timedelta(minutes=5)

N_PER_SENSOR = 3000
WARMUP = 1000

DOOR_OPEN_RATE = 0.05

EPISODE_KINDS = {
    "temperature_spike": {"length": (6, 12), "add": {"temperature": 9.0}},
    "power_surge": {"length": (6, 12), "add": {"power": 160.0}},
    "door_stuck": {
        "length": (8, 14),
        "add": {"temperature": 4.0, "humidity": 12.0},
        "set": {"door_open": 1},
    },
    "combined": {
        "length": (6, 12),
        "add": {"temperature": 6.0, "humidity": 18.0},
    },
    "single_mild": {"length": (1, 1), "add": {"temperature": 4.5}},
    "single_severe": {
        "length": (1, 1),
        "add": {"temperature": 14.0, "power": 220.0},
    },
}

KIND_ORDER = [
    "temperature_spike",
    "power_surge",
    "single_mild",
    "door_stuck",
    "single_severe",
    "combined",
]

# Held-out patterns: used ONLY for reporting, never to choose a setting.
HELDOUT_KINDS = {
    "gradual_drift": {"length": (24, 36), "ramp": {"temperature": 8.0}},
    "flatline": {"length": (12, 18), "flat": True},
}

HELDOUT_ORDER = [
    "gradual_drift",
    "flatline",
    "gradual_drift",
    "flatline",
    "gradual_drift",
    "flatline",
]


def _normal_arrays(n, rng):

    return {
        "temperature": rng.normal(22.0, 1.5, n),
        "humidity": rng.normal(45.0, 5.0, n),
        "door_open": (rng.random(n) < DOOR_OPEN_RATE).astype(int),
        "power": rng.normal(300.0, 25.0, n),
    }


def generate_normal_frame(n, seed):
    """Normal-only readings (no anomalies) for training/calibration."""

    rng = np.random.default_rng(seed)

    return pd.DataFrame(_normal_arrays(n, rng))[FEATURES]


def _plan_episodes(sensor_index, n, warmup, rng, kinds, kind_order):

    slots = len(kind_order)
    slot_len = (n - warmup) // slots

    shift = sensor_index % slots
    ordered = kind_order[shift:] + kind_order[:shift]

    plan = []

    for slot, kind in enumerate(ordered):

        low, high = kinds[kind]["length"]

        if slot_len < high + 60:
            raise ValueError("Stream too short for the episode plan.")

        length = int(rng.integers(low, high + 1))
        first = warmup + slot * slot_len
        start = first + int(rng.integers(20, slot_len - length - 40))

        plan.append((kind, start, start + length - 1))

    return plan


def build_stream(
    seed=STREAM_SEED,
    sensor_ids=SENSOR_IDS,
    n_per_sensor=N_PER_SENSOR,
    warmup=WARMUP,
    start=START_TIME,
    step=STEP,
    kinds=None,
    kind_order=None,
):
    """
    Return (readings, episodes).

    readings: list of dicts, sorted by (timestamp, sensor_id). They hold
              NO label information.
    episodes: ground truth with start/end index and time (inclusive).
    """

    kinds = EPISODE_KINDS if kinds is None else kinds
    kind_order = KIND_ORDER if kind_order is None else kind_order

    readings = []
    episodes = []

    for s_idx, sensor_id in enumerate(sensor_ids):

        rng = np.random.default_rng([seed, s_idx])

        data = _normal_arrays(n_per_sensor, rng)

        for kind, start_idx, end_idx in _plan_episodes(
            s_idx, n_per_sensor, warmup, rng, kinds, kind_order
        ):

            window = slice(start_idx, end_idx + 1)
            spec = kinds[kind]
            length = end_idx - start_idx + 1

            for feature, delta in spec.get("add", {}).items():
                data[feature][window] = data[feature][window] + delta

            for feature, delta in spec.get("ramp", {}).items():
                data[feature][window] = data[feature][window] + np.linspace(
                    0.0, delta, length
                )

            for feature, value in spec.get("set", {}).items():
                data[feature][window] = value

            if spec.get("flat"):
                for feature in FEATURES:
                    data[feature][window] = data[feature][start_idx]

            episodes.append(
                {
                    "sensor_id": sensor_id,
                    "kind": kind,
                    "start_idx": start_idx,
                    "end_idx": end_idx,
                    "start_time": start + start_idx * step,
                    "end_time": start + end_idx * step,
                }
            )

        for i in range(n_per_sensor):

            readings.append(
                {
                    "sensor_id": sensor_id,
                    "timestamp": start + i * step,
                    "temperature": float(data["temperature"][i]),
                    "humidity": float(data["humidity"][i]),
                    "door_open": int(data["door_open"][i]),
                    "power": float(data["power"][i]),
                }
            )

    readings.sort(key=lambda r: (r["timestamp"], r["sensor_id"]))

    return readings, episodes


def reading_to_array(reading):

    return np.array([[float(reading[f]) for f in FEATURES]])


def reading_to_json(reading):

    message = dict(reading)
    message["timestamp"] = reading["timestamp"].isoformat()

    return message


def reading_from_json(message):

    reading = dict(message)
    reading["timestamp"] = datetime.fromisoformat(message["timestamp"])

    if reading["timestamp"].tzinfo is None:
        reading["timestamp"] = reading["timestamp"].replace(tzinfo=UTC)

    reading["door_open"] = int(reading["door_open"])

    for feature in ("temperature", "humidity", "power"):
        reading[feature] = float(reading[feature])

    return reading


def publish_to_kafka(readings, bootstrap_servers, topic, delay_seconds=0.0):
    """Publish readings keyed by sensor_id. Raises if not all delivered."""

    from confluent_kafka import Producer

    producer = Producer(
        {
            "bootstrap.servers": bootstrap_servers,
            "enable.idempotence": True,
        }
    )

    failures = []

    def on_delivery(err, msg):
        if err is not None:
            failures.append(str(err))

    for reading in readings:

        value = json.dumps(reading_to_json(reading)).encode("utf-8")

        while True:
            try:
                producer.produce(
                    topic,
                    key=reading["sensor_id"],
                    value=value,
                    on_delivery=on_delivery,
                )
                break
            except BufferError:
                producer.poll(0.5)

        producer.poll(0)

        if delay_seconds:
            time.sleep(delay_seconds)

    remaining = producer.flush(30)

    if remaining or failures:
        raise RuntimeError(
            f"Kafka delivery incomplete: {remaining} queued, "
            f"{len(failures)} failed {failures[:3]}"
        )

    return len(readings)


def main(argv=None):

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument(
        "--bootstrap",
        default=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    )
    parser.add_argument(
        "--topic",
        default=os.environ.get("KAFKA_READINGS_TOPIC", "iot.sensor.reading"),
    )
    parser.add_argument("--delay-ms", type=float, default=0.0)
    parser.add_argument(
        "--sensors-config",
        default=str(CONFIG_PATH),
        help="config/sensors.json from python -m src.sensor_config",
    )
    parser.add_argument("--n-per-sensor", type=int, default=N_PER_SENSOR)
    parser.add_argument("--warmup", type=int, default=WARMUP)
    args = parser.parse_args(argv)

    sensor_ids = [s["sensor_id"] for s in load_sensors(args.sensors_config)]

    readings, episodes = build_stream(
        sensor_ids=sensor_ids,
        n_per_sensor=args.n_per_sensor,
        warmup=args.warmup,
    )

    print(
        f"sensors: {len(sensor_ids)}  readings: {len(readings)}  "
        f"injected episodes: {len(episodes)}"
    )

    for ep in episodes:
        print(
            f"{ep['sensor_id']}  {ep['kind']:<18} "
            f"{ep['start_time'].isoformat()} -> {ep['end_time'].isoformat()}"
        )

    if args.publish:
        count = publish_to_kafka(
            readings, args.bootstrap, args.topic, args.delay_ms / 1000.0
        )
        print(f"published {count} readings to {args.topic}")


if __name__ == "__main__":
    main()