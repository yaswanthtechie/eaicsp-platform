"""
Event-level evaluation of the streaming detector.

Uses eval_framework.event_scores for event precision/recall.
Detection delay is computed here (eval_framework has none).

Four labelled runs on the SAME stream, no winner picked:

    A  min_flagged_readings=1  tuner on
    B  min_flagged_readings=2  tuner on
    C  min_flagged_readings=1  threshold frozen
    D  min_flagged_readings=2  threshold frozen

Cost uses the project policy: missed episode 500, false-alarm event 2.

Run:
    python -m src.stream_eval
    python -m src.stream_eval --events-file output\\stream_events.jsonl
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from eval_framework import event_scores

from .auto_threshold import SignificanceThresholdTuner, robust_scale
from .episode_detector import EpisodeDetector
from .stream_model import train_stream_model
from .stream_processor import InMemoryPublisher, InMemoryWriter, StreamProcessor
from .stream_simulator import FEATURES, START_TIME, STEP, build_stream


PERCENTILE = 97.0
GAP = 3 * STEP
SEVERE_MARGIN = 3.0
MISS_COST = 500
FALSE_ALARM_COST = 2

RUNS = [
    ("A", 1, True),
    ("B", 2, True),
    ("C", 1, False),
    ("D", 2, False),
]

project_root = Path(__file__).resolve().parent.parent
output_dir = project_root / "output"


def _idx(timestamp, start, step):
    return (timestamp - start) // step


def _median(values):
    return float(np.median(values)) if values else None


def evaluate_events(
    events,
    episodes,
    n_per_sensor,
    start=START_TIME,
    step=STEP,
):
    """Event-level metrics + detection delay against injected episodes."""

    y_true = {s: np.zeros(n, dtype=int) for s, n in n_per_sensor.items()}
    y_pred = {s: np.zeros(n, dtype=int) for s, n in n_per_sensor.items()}

    for ep in episodes:
        y_true[ep["sensor_id"]][ep["start_idx"]: ep["end_idx"] + 1] = 1

    parsed = []

    for event in events:

        p = event["payload"]
        sensor = p["sensor_id"]
        n = n_per_sensor[sensor]

        ws = _idx(datetime.fromisoformat(p["window_start"]), start, step)
        we = _idx(datetime.fromisoformat(p["window_end"]), start, step)

        y_pred[sensor][max(ws, 0): min(we, n - 1) + 1] = 1

        parsed.append(
            {
                "sensor_id": sensor,
                "ws": ws,
                "we": we,
                "first": datetime.fromisoformat(p["first_flag_time"]),
                "confirmed": datetime.fromisoformat(p["confirmed_time"]),
            }
        )

    totals = {"n_true": 0, "n_pred": 0, "detected": 0, "false_alarms": 0}

    for sensor in n_per_sensor:

        scores = event_scores(y_true[sensor], y_pred[sensor])

        totals["n_true"] += scores["n_true_events"]
        totals["n_pred"] += scores["n_pred_events"]
        totals["detected"] += scores["events_detected"]
        totals["false_alarms"] += scores["false_alarm_events"]

    if totals["n_pred"] != len(events):
        raise RuntimeError(
            "Published events merged in the 0/1 encoding "
            f"({totals['n_pred']} vs {len(events)}); check the gap setting."
        )

    delays_first = []
    delays_confirm = []
    matches_per_detected = []
    by_kind = {}

    detected_mine = 0

    for ep in episodes:

        kind_counts = by_kind.setdefault(ep["kind"], [0, 0])
        kind_counts[1] += 1

        matches = [
            e
            for e in parsed
            if e["sensor_id"] == ep["sensor_id"]
            and e["ws"] <= ep["end_idx"]
            and e["we"] >= ep["start_idx"]
        ]

        if not matches:
            continue

        detected_mine += 1
        kind_counts[0] += 1
        matches_per_detected.append(len(matches))

        first = min(matches, key=lambda e: e["first"])

        delays_first.append(
            (first["first"] - ep["start_time"]).total_seconds() / 60.0
        )
        delays_confirm.append(
            (first["confirmed"] - ep["start_time"]).total_seconds() / 60.0
        )

    if detected_mine != totals["detected"]:
        raise RuntimeError(
            "Overlap check disagrees with eval_framework.event_scores: "
            f"{detected_mine} vs {totals['detected']}."
        )

    n_pred = totals["n_pred"]
    missed = totals["n_true"] - totals["detected"]

    return {
        "true_episodes": totals["n_true"],
        "detected": totals["detected"],
        "missed": missed,
        "published_events": n_pred,
        "false_alarm_events": totals["false_alarms"],
        "event_precision": (
            (n_pred - totals["false_alarms"]) / n_pred if n_pred else None
        ),
        "event_recall": (
            totals["detected"] / totals["n_true"] if totals["n_true"] else None
        ),
        "events_per_detected_episode": (
            float(np.mean(matches_per_detected)) if matches_per_detected else None
        ),
        "median_delay_first_flag_min": _median(delays_first),
        "median_delay_confirmed_min": _median(delays_confirm),
        "max_delay_confirmed_min": (
            max(delays_confirm) if delays_confirm else None
        ),
        "episode_cost": missed * MISS_COST + totals["false_alarms"] * FALSE_ALARM_COST,
        "by_kind": {k: tuple(v) for k, v in by_kind.items()},
    }


def run_once(readings, scores, episodes, model, min_flagged, tuner_on, n_per_sensor):

    tuner = SignificanceThresholdTuner(
        model.calibration_scores, percentile=PERCENTILE
    )

    detector = EpisodeDetector(
        gap=GAP,
        scale=robust_scale(model.calibration_scores),
        min_flagged_readings=min_flagged,
        severe_margin=SEVERE_MARGIN,
    )

    publisher = InMemoryPublisher()

    processor = StreamProcessor(
        model,
        tuner,
        detector,
        InMemoryWriter(),
        publisher,
        use_tuner=tuner_on,
    )

    threshold_start = tuner.threshold

    for reading, score in zip(readings, scores):
        processor.handle(reading, score=float(score))

    processor.finish()

    metrics = evaluate_events(publisher.events, episodes, n_per_sensor)

    state = tuner.get_state()

    metrics.update(
        {
            "dropped_candidates": detector.dropped_candidates,
            "flagged_readings": processor.flagged_count,
            "threshold_start": threshold_start,
            "threshold_end": tuner.threshold,
            "tuner_adaptations": state["adaptations"],
            "tuner_freezes": state["freezes"],
        }
    )

    return metrics, processor, publisher


def _row(label, min_flagged, tuner_on, metrics):

    row = {
        "run": label,
        "min_flagged_readings": min_flagged,
        "threshold": tuner_on,
    }

    row.update({k: v for k, v in metrics.items() if k != "by_kind"})

    return row


def _print_table(rows):

    frame = pd.DataFrame(rows)

    print(frame.round(4).T.to_string(header=False))

    return frame


def main(argv=None):

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events-file", default=None)
    args = parser.parse_args(argv)

    readings, episodes = build_stream()

    n_per_sensor = {}

    for r in readings:
        n_per_sensor[r["sensor_id"]] = n_per_sensor.get(r["sensor_id"], 0) + 1

    if args.events_file:

        with open(args.events_file, encoding="utf-8") as handle:
            events = [json.loads(line) for line in handle if line.strip()]

        metrics = evaluate_events(events, episodes, n_per_sensor)

        print("REAL RUN (events from Kafka consumer)")
        _print_table([_row("real", None, "tuner on", metrics)])

        return

    model = train_stream_model()

    X = np.array([[r[f] for f in FEATURES] for r in readings])
    scores = model.score_batch(X)

    rows = []
    kind_rows = []

    for label, min_flagged, tuner_on in RUNS:

        metrics, _, _ = run_once(
            readings, scores, episodes, model, min_flagged, tuner_on, n_per_sensor
        )

        tuner_text = "tuner on" if tuner_on else "frozen"

        rows.append(_row(label, min_flagged, tuner_text, metrics))

        for kind, (detected, total) in metrics["by_kind"].items():
            kind_rows.append(
                {
                    "run": label,
                    "kind": kind,
                    "detected": detected,
                    "total": total,
                }
            )

    print(
        f"seeds: train/calibration/stream differ; percentile={PERCENTILE}; "
        f"gap={GAP}; severe_margin={SEVERE_MARGIN}"
    )

    frame = _print_table(rows)

    kinds = pd.DataFrame(kind_rows)
    kinds["recall"] = kinds["detected"] / kinds["total"]

    print()
    print(kinds.pivot(index="kind", columns="run", values="recall").round(3).to_string())

    output_dir.mkdir(parents=True, exist_ok=True)

    frame.to_csv(output_dir / "stream_eval_results.csv", index=False)
    kinds.to_csv(output_dir / "stream_eval_by_kind.csv", index=False)

    print("\nwritten: output/stream_eval_results.csv, output/stream_eval_by_kind.csv")


if __name__ == "__main__":
    main()