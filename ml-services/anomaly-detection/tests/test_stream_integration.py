import json
import os
import uuid

import pytest
from dotenv import load_dotenv

from src.stream_consumer import load_settings, run
from src.stream_simulator import build_stream, publish_to_kafka

load_dotenv()

pytestmark = pytest.mark.integration


def test_readings_reach_influx_and_one_event_per_episode(tmp_path):

    if not os.environ.get("INFLUXDB_TOKEN"):
        pytest.fail(
            "INFLUXDB_TOKEN not set; copy .env.example to .env and start "
            "docker-compose.stream.yml"
        )

    from influxdb_client import InfluxDBClient

    sensor = f"it-{uuid.uuid4().hex[:8]}"
    readings, episodes = build_stream(
        sensor_ids=[sensor], n_per_sensor=700, warmup=200
    )

    settings = load_settings()
    settings["group_id"] = f"it-{uuid.uuid4().hex[:8]}"

    publish_to_kafka(
        readings, settings["bootstrap_servers"], settings["readings_topic"]
    )

    events_log = tmp_path / "events.jsonl"

    run(
        settings,
        sensor_map={sensor: "WH-BLR-01"},
        events_log=str(events_log),
        idle_exit=10,
        flush_open_episodes=True,
    )

    with InfluxDBClient(
        url=settings["influx_url"],
        token=settings["influx_token"],
        org=settings["influx_org"],
    ) as client:

        flux = '''
        from(bucket: p_bucket)
          |> range(start: 2026-01-01T00:00:00Z, stop: 2027-01-01T00:00:00Z)
          |> filter(fn: (r) => r._measurement == "warehouse_sensor"
                             and r._field == "is_flagged"
                             and r.sensor_id == p_sensor)
          |> count()
        '''

        tables = client.query_api().query(
            flux,
            params={"p_bucket": settings["influx_bucket"], "p_sensor": sensor},
        )

        stored = sum(rec.get_value() for t in tables for rec in t.records)

    assert stored == len(readings)

    events = [
        json.loads(line)
        for line in events_log.read_text().splitlines()
        if line.strip()
    ]

    ours = [e for e in events if e["payload"]["sensor_id"] == sensor]

    assert ours, "no anomaly events published"
    assert len({e["payload"]["episode_id"] for e in ours}) == len(ours)

    for e in ours:
        assert e["event_type"] == "iot.anomaly.detected"
        assert e["payload"]["top_features"]