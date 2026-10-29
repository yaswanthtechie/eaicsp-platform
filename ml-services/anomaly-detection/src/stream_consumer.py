"""
Kafka -> (InfluxDB + anomaly scoring) -> Kafka consumer.

All I/O lives here. Logic lives in stream_processor.py.

Delivery: at-least-once. Offsets are committed only when no sensor has an
open or candidate episode. After a crash, replay from the last commit
rebuilds the same episodes with the same episode_id, and consumers
de-duplicate on payload.episode_id. InfluxDB writes are idempotent (same
tag + timestamp overwrites). The threshold tuner restarts from its
calibration state (not persisted).

Invalid messages are logged and skipped. Duplicate or late readings are
skipped before scoring. Readings from sensors missing from the sensor
config are counted and skipped, so every event has a canonical
warehouse_id (contract: contracts/events/iot.anomaly.detected.v1.json).
A sensor map is required: the consumer never emits an event without one.

Run:
    python -m src.stream_consumer --idle-exit 30 --flush-open-episodes --events-log output\\stream_events.jsonl
"""

import argparse
import json
import logging
import math
import os
import re
import time
from datetime import UTC
from pathlib import Path

from .auto_threshold import SignificanceThresholdTuner, robust_scale
from .episode_detector import EpisodeDetector
from .sensor_config import CONFIG_PATH, load_sensors, sensor_map as build_sensor_map
from .stream_events import EVENT_TYPE, event_key
from .stream_model import load_stream_model
from .stream_processor import StreamProcessor
from .stream_simulator import STEP, reading_from_json


log = logging.getLogger(__name__)

PERCENTILE = 97.0
GAP = 3 * STEP
SEVERE_MARGIN = 3.0
COMMIT_EVERY = 100

REQUIRED_FIELDS = (
    "sensor_id",
    "timestamp",
    "temperature",
    "humidity",
    "door_open",
    "power",
)

# Safe for an InfluxDB tag and a Kafka key: letters, digits, dot, underscore,
# hyphen, 1-64 chars. No spaces, commas, newlines or other control characters.
SENSOR_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,64}")


class InvalidReading(ValueError):
    """A message that can never be processed. Skip it; never retry it."""


def load_settings(env=None):

    env = os.environ if env is None else env

    token = env.get("INFLUXDB_TOKEN")

    if not token:
        raise RuntimeError(
            "INFLUXDB_TOKEN is not set. Copy .env.example to .env and fill it in."
        )

    return {
        "bootstrap_servers": env.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "group_id": env.get("KAFKA_GROUP_ID", "iot-anomaly-consumer-v1"),
        "readings_topic": env.get("KAFKA_READINGS_TOPIC", "iot.sensor.reading"),
        "events_topic": env.get("KAFKA_EVENTS_TOPIC", EVENT_TYPE),
        "influx_url": env.get("INFLUXDB_URL", "http://localhost:8086"),
        "influx_token": token,
        "influx_org": env.get("INFLUXDB_ORG", "eaicsp"),
        "influx_bucket": env.get("INFLUXDB_BUCKET", "iot_sensors"),
    }


def parse_message(value):

    try:
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8")

        message = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise InvalidReading(f"not valid JSON: {exc}") from exc

    if not isinstance(message, dict):
        raise InvalidReading("message is not a JSON object")

    missing = [f for f in REQUIRED_FIELDS if f not in message]

    if missing:
        raise InvalidReading(f"missing fields: {missing}")

    sensor_id = message["sensor_id"]

    if not isinstance(sensor_id, str) or not SENSOR_ID_PATTERN.fullmatch(sensor_id):
        raise InvalidReading(f"bad sensor_id: {sensor_id!r:.80}")

    door_open = message["door_open"]

    if type(door_open) is not int or door_open not in (0, 1):
        raise InvalidReading(
            f"door_open must be the integer 0 or 1, got {door_open!r:.80}"
        )

    try:
        reading = reading_from_json(message)
    except (TypeError, ValueError) as exc:
        raise InvalidReading(f"bad field value: {exc}") from exc

    for feature in ("temperature", "humidity", "power"):
        if not math.isfinite(reading[feature]):
            raise InvalidReading(f"{feature} is not a finite number")

    return reading


def _escape_tag(value):

    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(" ", "\\ ")
        .replace("=", "\\=")
    )


def to_line_protocol(reading, score, flagged):
    """InfluxDB line protocol, second precision."""

    fields = ",".join(
        [
            f"temperature={float(reading['temperature'])!r}",
            f"humidity={float(reading['humidity'])!r}",
            f"door_open={int(reading['door_open'])}i",
            f"power={float(reading['power'])!r}",
            f"anomaly_score={float(score)!r}",
            f"is_flagged={int(bool(flagged))}i",
        ]
    )

    timestamp = int(reading["timestamp"].astimezone(UTC).timestamp())

    return (
        f"warehouse_sensor,sensor_id={_escape_tag(reading['sensor_id'])} "
        f"{fields} {timestamp}"
    )


class InfluxWriter:

    def __init__(self, url, token, org, bucket):

        if not token:
            raise ValueError("INFLUXDB_TOKEN is not set.")

        from influxdb_client import InfluxDBClient, WritePrecision
        from influxdb_client.client.write_api import SYNCHRONOUS

        self._precision = WritePrecision.S
        self._org = org
        self._bucket = bucket
        self._client = InfluxDBClient(url=url, token=token, org=org)
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)

    def write(self, reading, score, flagged):

        self._write_api.write(
            bucket=self._bucket,
            org=self._org,
            record=to_line_protocol(reading, score, flagged),
            write_precision=self._precision,
        )

    def close(self):
        self._client.close()


class KafkaEventPublisher:

    def __init__(self, bootstrap_servers, topic, flush_timeout=10.0):

        from confluent_kafka import Producer

        self._producer = Producer(
            {
                "bootstrap.servers": bootstrap_servers,
                "enable.idempotence": True,
            }
        )
        self._topic = topic
        self._timeout = flush_timeout

    def publish(self, event, attempts=3, backoff_seconds=2.0):

        last_error = None

        for attempt in range(1, attempts + 1):

            errors = []

            def on_delivery(err, msg):
                if err is not None:
                    errors.append(str(err))

            self._producer.produce(
                self._topic,
                key=event_key(event),
                value=json.dumps(event).encode("utf-8"),
                on_delivery=on_delivery,
            )

            remaining = self._producer.flush(self._timeout)

            if not remaining and not errors:
                return

            last_error = f"{remaining} unacknowledged, {errors}"
            time.sleep(backoff_seconds * attempt)

        raise RuntimeError(
            f"Event delivery failed after {attempts} attempts: {last_error}"
        )

    def close(self):
        self._producer.flush(self._timeout)


class JsonlEventLog:
    """Append-only event log, de-duplicated on payload.episode_id."""

    def __init__(self, path):

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        self._seen = set()

        if path.exists():
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        self._seen.add(json.loads(line)["payload"]["episode_id"])
                    except (ValueError, KeyError, TypeError):
                        continue

        self._file = open(path, "a", encoding="utf-8")

    def publish(self, event):

        episode_id = event["payload"]["episode_id"]

        if episode_id in self._seen:
            return

        self._seen.add(episode_id)
        self._file.write(json.dumps(event) + "\n")
        self._file.flush()

    def close(self):
        self._file.close()


class MultiPublisher:

    def __init__(self, *publishers):
        self._publishers = publishers

    def publish(self, event):
        for publisher in self._publishers:
            publisher.publish(event)

    def close(self):
        for publisher in self._publishers:
            publisher.close()


def build_processor(settings, model, writer, publisher, sensor_map):

    if not sensor_map:
        raise ValueError(
            "sensor_map is required: every event needs a canonical warehouse_id."
        )

    tuner = SignificanceThresholdTuner(
        model.calibration_scores, percentile=PERCENTILE
    )

    detector = EpisodeDetector(
        gap=GAP,
        scale=robust_scale(model.calibration_scores),
        min_flagged_readings=2,
        severe_margin=SEVERE_MARGIN,
    )

    return StreamProcessor(
        model, tuner, detector, writer, publisher, sensor_map=sensor_map
    )


def run(
    settings,
    *,
    sensor_map,
    events_log=None,
    idle_exit=None,
    flush_open_episodes=False,
):

    from confluent_kafka import Consumer, KafkaError, KafkaException

    model = load_stream_model()
    model.warm_up()
    log.info("consumer ready")

    writer = InfluxWriter(
        settings["influx_url"],
        settings["influx_token"],
        settings["influx_org"],
        settings["influx_bucket"],
    )

    publishers = [
        KafkaEventPublisher(
            settings["bootstrap_servers"], settings["events_topic"]
        )
    ]

    if events_log:
        publishers.append(JsonlEventLog(events_log))

    publisher = MultiPublisher(*publishers)

    processor = build_processor(
        settings, model, writer, publisher, sensor_map=sensor_map
    )

    consumer = Consumer(
        {
            "bootstrap.servers": settings["bootstrap_servers"],
            "group.id": settings["group_id"],
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )

    consumer.subscribe([settings["readings_topic"]])

    last_message = None
    processed = 0
    skipped = 0
    since_commit = 0

    try:
        try:
            while True:

                msg = consumer.poll(1.0)

                if msg is None:
                    if (
                        idle_exit
                        and last_message is not None
                        and time.monotonic() - last_message > idle_exit
                    ):
                        break
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    raise KafkaException(msg.error())

                last_message = time.monotonic()

                try:
                    reading = parse_message(msg.value())
                except InvalidReading as exc:
                    skipped += 1
                    log.warning(
                        "Skipping invalid reading %s[%d]@%d: %s",
                        msg.topic(),
                        msg.partition(),
                        msg.offset(),
                        exc,
                    )
                    continue

                processor.handle(reading)

                processed += 1
                since_commit += 1

                # Commit only at a safe point: no open/candidate episode.
                if (
                    since_commit >= COMMIT_EVERY
                    and not processor.detector.has_open_state()
                ):
                    consumer.commit(message=msg, asynchronous=False)
                    since_commit = 0

        except KeyboardInterrupt:
            pass

        if flush_open_episodes:
            # Only when the stream is truly finished (e.g. a batch replay).
            processor.finish()

        if not processor.detector.has_open_state():
            try:
                consumer.commit(asynchronous=False)
            except KafkaException:
                pass
        # else: keep the last safe commit; the next run replays and
        # rebuilds the open episode with the same episode_id.

    finally:
        consumer.close()
        writer.close()
        publisher.close()

    print(
        f"processed={processed} skipped_invalid={skipped} "
        f"skipped_stale={processor.skipped_stale} "
        f"skipped_unknown_sensor={processor.skipped_unknown} "
        f"flagged={processor.flagged_count} "
        f"episodes={processor.detector.episodes_emitted} "
        f"dropped_candidates={processor.detector.dropped_candidates} "
        f"final_threshold={processor.tuner.threshold:.6f}"
    )


def main(argv=None):

    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--idle-exit", type=float, default=None)
    parser.add_argument("--events-log", default=None)
    parser.add_argument("--group-id", default=None)
    parser.add_argument("--flush-open-episodes", action="store_true")
    parser.add_argument("--sensors-config", default=str(CONFIG_PATH))
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)

    settings = load_settings()

    if args.group_id:
        settings["group_id"] = args.group_id

    sensor_map = build_sensor_map(load_sensors(args.sensors_config))

    run(
        settings,
        sensor_map=sensor_map,
        events_log=args.events_log,
        idle_exit=args.idle_exit,
        flush_open_episodes=args.flush_open_episodes,
    )


if __name__ == "__main__":
    main()