"""
On-demand demo episode for the live dashboard.

Publishes one anomaly episode for one sensor in a single batch (8 flagged
readings 10 seconds apart, then a closing reading stamped 16 minutes after
the last flag, so the detector closes the episode at once) and measures how
long the event takes to arrive on iot.anomaly.detected.

"Episode start" = the moment the first anomalous reading is handed to Kafka.
A real live episode closes only after the 15-minute quiet gap; the demo uses
sensor-time timestamps to close it immediately.

Timestamps end "now". The detector skips readings that are not later than
the last one it saw for a sensor, so a sensor can be used again only after
its previous episode's time span (about 17 minutes). The script remembers
this in output/demo_state.json and picks a free sensor.

Run (stack up, anomaly-detector running, from ml-services/anomaly-detection):
    python -m src.demo_anomaly
    python -m src.demo_anomaly --sensor WH-BLR-01-S1
"""

import argparse
import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .sensor_config import CONFIG_PATH, load_sensors
from .stream_consumer import GAP
from .stream_events import EVENT_TYPE, make_episode_id
from .stream_simulator import publish_to_kafka


EPISODE_READINGS = 8
EPISODE_STEP = timedelta(seconds=10)
CLOSING_GAP = GAP + timedelta(minutes=1)
SPAN = (EPISODE_READINGS - 1) * EPISODE_STEP + CLOSING_GAP
COOLDOWN = SPAN + timedelta(minutes=1)
MAX_SECONDS = 5.0

NORMAL = {"temperature": 22.0, "humidity": 45.0, "door_open": 0, "power": 300.0}
SPIKE = {"temperature": 31.0}

project_root = Path(__file__).resolve().parent.parent
STATE_PATH = project_root / "output" / "demo_state.json"


def load_state(path=STATE_PATH):

    path = Path(path)

    if not path.is_file():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}

    return {k: float(v) for k, v in data.items()}


def save_state(state, path=STATE_PATH):

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def pick_sensor(sensors, state, now=None):
    """The sensor used longest ago, if it is past its cooldown."""

    now = (now or datetime.now(UTC)).timestamp()
    ready = [
        s["sensor_id"]
        for s in sensors
        if now - state.get(s["sensor_id"], 0.0) >= COOLDOWN.total_seconds()
    ]

    if not ready:
        raise RuntimeError(
            f"Every sensor was used in the last {COOLDOWN.total_seconds() / 60:.0f} "
            "minutes. Wait a little, or pass --sensor."
        )

    return min(ready, key=lambda s: state.get(s, 0.0))


def build_demo_readings(sensor_id, end=None, n=EPISODE_READINGS):
    """Return (readings, expected_episode_id). The last reading is at `end`."""

    end = (end or datetime.now(UTC)).replace(microsecond=0)
    last_flag = end - CLOSING_GAP
    first = last_flag - (n - 1) * EPISODE_STEP

    readings = [
        {
            "sensor_id": sensor_id,
            "timestamp": first + i * EPISODE_STEP,
            **{**NORMAL, **SPIKE},
        }
        for i in range(n)
    ]

    readings.append({"sensor_id": sensor_id, "timestamp": end, **NORMAL})

    return readings, make_episode_id(sensor_id, first)


def ensure_topics(bootstrap, topics):

    from confluent_kafka.admin import AdminClient, NewTopic

    admin = AdminClient({"bootstrap.servers": bootstrap})
    existing = admin.list_topics(timeout=10).topics
    missing = [
        NewTopic(t, num_partitions=1, replication_factor=1)
        for t in topics
        if t not in existing
    ]

    for future in admin.create_topics(missing).values() if missing else []:
        try:
            future.result()
        except Exception:
            pass


def run_demo(bootstrap, readings_topic, events_topic, sensor_id, timeout=30.0):
    """Publish the episode and return timing, or None if no event arrived."""

    from confluent_kafka import Consumer, TopicPartition

    ensure_topics(bootstrap, [readings_topic, events_topic])

    readings, expected = build_demo_readings(sensor_id)

    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap,
            "group.id": f"demo-{uuid.uuid4().hex[:8]}",
            "enable.auto.commit": False,
        }
    )

    try:
        partitions = (
            consumer.list_topics(events_topic, timeout=10)
            .topics[events_topic]
            .partitions
        )

        consumer.assign(
            [
                TopicPartition(
                    events_topic,
                    p,
                    consumer.get_watermark_offsets(
                        TopicPartition(events_topic, p), timeout=10
                    )[1],
                )
                for p in partitions
            ]
        )

        t0 = time.monotonic()
        publish_to_kafka(readings, bootstrap, readings_topic)
        t_published = time.monotonic()

        while time.monotonic() < t0 + timeout:

            msg = consumer.poll(0.2)

            if msg is None or msg.error():
                continue

            arrived = time.monotonic()

            try:
                event = json.loads(msg.value())
            except ValueError:
                continue

            payload = event.get("payload", {})

            if payload.get("episode_id") == expected:
                return {
                    "sensor_id": sensor_id,
                    "episode_id": expected,
                    "publish_seconds": t_published - t0,
                    "event_seconds": arrived - t0,
                    "severity": payload.get("severity"),
                    "warehouse_id": payload.get("warehouse_id"),
                    "message": payload.get("message"),
                }

        return None

    finally:
        consumer.close()


def main(argv=None):

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bootstrap",
        default=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092"),
    )
    parser.add_argument(
        "--readings-topic",
        default=os.environ.get("KAFKA_READINGS_TOPIC", "iot.sensor.reading"),
    )
    parser.add_argument(
        "--events-topic", default=os.environ.get("KAFKA_EVENTS_TOPIC", EVENT_TYPE)
    )
    parser.add_argument("--sensors-config", default=str(CONFIG_PATH))
    parser.add_argument("--sensor", default=None)
    parser.add_argument("--max-seconds", type=float, default=MAX_SECONDS)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)

    sensors = load_sensors(args.sensors_config)
    state = load_state()

    try:
        sensor_id = args.sensor or pick_sensor(sensors, state)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    if sensor_id not in {s["sensor_id"] for s in sensors}:
        print(f"FAIL: unknown sensor {sensor_id}")
        return 2

    print(f"injecting episode on {sensor_id} (the detector must be running)")

    state[sensor_id] = datetime.now(UTC).timestamp()
    save_state(state)

    result = run_demo(
        args.bootstrap,
        args.readings_topic,
        args.events_topic,
        sensor_id,
        args.timeout,
    )

    if result is None:
        print(
            f"FAIL: no event for the episode within {args.timeout:.0f}s. Is "
            "anomaly-detector running and caught up?"
        )
        return 1

    print(f"episode_id    : {result['episode_id']}")
    print(f"warehouse     : {result['warehouse_id']}   severity: {result['severity']}")
    print(f"message       : {result['message']}")
    print(f"published in  : {result['publish_seconds']:.2f}s")
    print(f"event arrived : {result['event_seconds']:.2f}s after episode start")

    if result["event_seconds"] > args.max_seconds:
        print(f"FAIL: slower than {args.max_seconds:.1f}s")
        return 1

    print(f"OK: within {args.max_seconds:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())