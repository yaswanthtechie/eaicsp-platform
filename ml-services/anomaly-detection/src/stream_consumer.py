"""
Kafka -> (InfluxDB + anomaly scoring) -> Kafka consumer.

All I/O lives here. Logic lives in stream_processor.py.

Delivery: at-least-once. Offsets are committed after processing.
InfluxDB writes are idempotent (same tag + timestamp overwrites) and
events carry a deterministic payload.episode_id for de-duplication.
Detector state is in memory: after a restart it is rebuilt by replaying
from the last committed offset.

Run:
    python -m src.stream_consumer --idle-exit 30 --events-log output\\stream_events.jsonl
"""

import argparse
import json
import os
import time
from datetime import UTC
from pathlib import Path

from .auto_threshold import SignificanceThresholdTuner, robust_scale
from .episode_detector import EpisodeDetector
from .stream_events import EVENT_TYPE, event_key
from .stream_model import load_or_train
from .stream_processor import StreamProcessor
from .stream_simulator import STEP, reading_from_json


PERCENTILE = 97.0
GAP = 3 * STEP
SEVERE_MARGIN = 3.0
COMMIT_EVERY = 100


def load_settings(env=None):

    env = os.environ if env is None else env

    return {
        "bootstrap_servers": env.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "group_id": env.get("KAFKA_GROUP_ID", "iot-anomaly-consumer-v1"),
        "readings_topic": env.get("KAFKA_READINGS_TOPIC", "iot.sensor.reading"),
        "events_topic": env.get("KAFKA_EVENTS_TOPIC", EVENT_TYPE),
        "influx_url": env.get("INFLUXDB_URL", "http://localhost:8086"),
        "influx_token": env.get("INFLUXDB_TOKEN", ""),
        "influx_org": env.get("INFLUXDB_ORG", "eaicsp"),
        "influx_bucket": env.get("INFLUXDB_BUCKET", "iot_sensors"),
    }


def parse_message(value):

    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")

    return reading_from_json(json.loads(value))


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

    def publish(self, event):

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

        if remaining or errors:
            raise RuntimeError(
                f"Event delivery failed: {remaining} unacknowledged, {errors}"
            )

    def close(self):
        self._producer.flush(self._timeout)


class JsonlEventLog:

    def __init__(self, path):

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        self._file = open(path, "a", encoding="utf-8")

    def publish(self, event):

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


def build_processor(settings, model, writer, publisher):

    tuner = SignificanceThresholdTuner(
        model.calibration_scores, percentile=PERCENTILE
    )

    detector = EpisodeDetector(
        gap=GAP,
        scale=robust_scale(model.calibration_scores),
        min_flagged_readings=2,
        severe_margin=SEVERE_MARGIN,
    )

    return StreamProcessor(model, tuner, detector, writer, publisher)


def run(settings, events_log=None, idle_exit=None):

    from confluent_kafka import Consumer, KafkaError, KafkaException

    model = load_or_train()

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

    processor = build_processor(settings, model, writer, publisher)

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

                processor.handle(parse_message(msg.value()))

                processed += 1
                last_message = time.monotonic()

                if processed % COMMIT_EVERY == 0:
                    consumer.commit(message=msg, asynchronous=False)

        except KeyboardInterrupt:
            pass

        processor.finish()

        try:
            consumer.commit(asynchronous=False)
        except KafkaException:
            pass

    finally:
        consumer.close()
        writer.close()
        publisher.close()

    print(
        f"processed={processed} flagged={processor.flagged_count} "
        f"episodes={processor.detector.episodes_emitted} "
        f"dropped_candidates={processor.detector.dropped_candidates} "
        f"final_threshold={processor.tuner.threshold:.6f}"
    )


def main(argv=None):

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--idle-exit", type=float, default=None)
    parser.add_argument("--events-log", default=None)
    parser.add_argument("--group-id", default=None)
    args = parser.parse_args(argv)

    settings = load_settings()

    if args.group_id:
        settings["group_id"] = args.group_id

    run(settings, events_log=args.events_log, idle_exit=args.idle_exit)


if __name__ == "__main__":
    main()