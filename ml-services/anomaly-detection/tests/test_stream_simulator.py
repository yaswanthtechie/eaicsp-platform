import json

import numpy as np

from src.stream_simulator import (
    CALIBRATION_SEED,
    FEATURES,
    N_PER_SENSOR,
    SENSOR_IDS,
    START_TIME,
    STEP,
    STREAM_SEED,
    TRAIN_SEED,
    WARMUP,
    build_stream,
    generate_normal_frame,
    reading_from_json,
    reading_to_json,
)


def test_seeds_are_distinct():

    assert len({TRAIN_SEED, CALIBRATION_SEED, STREAM_SEED}) == 3


def test_stream_is_deterministic():

    r1, e1 = build_stream()
    r2, e2 = build_stream()

    assert r1 == r2
    assert e1 == e2


def test_counts_and_order():

    readings, episodes = build_stream()

    assert len(readings) == len(SENSOR_IDS) * N_PER_SENSOR
    assert len(episodes) == len(SENSOR_IDS) * 6

    keys = [(r["timestamp"], r["sensor_id"]) for r in readings]

    assert keys == sorted(keys)
    assert all(r["timestamp"].tzinfo is not None for r in readings)


def test_episodes_after_warmup_and_separated():

    _, episodes = build_stream()

    for sensor in SENSOR_IDS:

        own = sorted(
            (e for e in episodes if e["sensor_id"] == sensor),
            key=lambda e: e["start_idx"],
        )

        assert own[0]["start_idx"] >= WARMUP

        for a, b in zip(own, own[1:]):
            assert b["start_idx"] - a["end_idx"] >= 40

        for e in own:
            assert e["end_idx"] < N_PER_SENSOR
            assert e["end_time"] == START_TIME + e["end_idx"] * STEP


def test_single_reading_episodes_exist():

    _, episodes = build_stream()

    kinds = [e["kind"] for e in episodes if e["start_idx"] == e["end_idx"]]

    assert kinds.count("single_mild") == len(SENSOR_IDS)
    assert kinds.count("single_severe") == len(SENSOR_IDS)


def test_episode_values_are_elevated():

    readings, episodes = build_stream()

    lookup = {(r["sensor_id"], r["timestamp"]): r for r in readings}

    for e in episodes:

        if e["kind"] != "temperature_spike":
            continue

        values = [
            lookup[(e["sensor_id"], START_TIME + i * STEP)]["temperature"]
            for i in range(e["start_idx"], e["end_idx"] + 1)
        ]

        assert np.mean(values) > 28


def test_readings_hold_no_labels():

    readings, _ = build_stream()

    assert set(readings[0]) == {"sensor_id", "timestamp", *FEATURES}


def test_json_roundtrip():

    readings, _ = build_stream()

    for r in readings[:20]:
        assert reading_from_json(json.loads(json.dumps(reading_to_json(r)))) == r


def test_normal_frame_shape_and_binary_door():

    frame = generate_normal_frame(500, TRAIN_SEED)

    assert list(frame.columns) == FEATURES
    assert len(frame) == 500
    assert set(frame["door_open"].unique()) <= {0, 1}