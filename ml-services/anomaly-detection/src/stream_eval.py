"""
Event-level evaluation of the streaming detector.

Uses eval_framework.event_scores for event precision/recall.
Detection delay is computed here (eval_framework has none).

Four labelled runs on the SAME stream, no winner picked:

    A  min_flagged_readings=1  tuner on
    B  min_flagged_readings=2  tuner on
    C  min_flagged_readings=1  threshold frozen
    D  min_flagged_readings=2  threshold frozen

Held-out patterns (gradual drift, flatline) are reported separately with
run B settings and are never used to choose a setting.

Cost uses the project policy: missed episode 500, false-alarm event 2.
Evaluates the SAVED model (python -m src.train_stream_model).
Results go to results/ (tracked); MLflow: anomaly-detection-r14-streaming.

Run:
    python -m src.stream_eval
    python -m src.stream_eval --extra-percentile 99
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
from .stream_model import load_stream_model
from .stream_processor import InMemoryPublisher, InMemoryWriter, StreamProcessor
from .stream_simulator import (
    EPISODE_KINDS,
    FEATURES,
    HELDOUT_KINDS,
    HELDOUT_ORDER,
    START_TIME,
    STEP,
    STREAM_SEED,
    build_stream,
)


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

MLFLOW_URI = "sqlite:///mlflow.db"
MLFLOW_EXPERIMENT = "anomaly-detection-r14-streaming"

project_root = Path(__file__).resolve().parent.parent
results_dir = project_root / "results"


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

    # De-duplicate on episode_id, the same way downstream consumers will.
    unique = {}

    for event in events:
        unique.setdefault(event["payload"]["episode_id"], event)

    events = list(unique.values())

    y_true = {s: np.zeros(n, dtype=int) for s, n in n_per_sensor.items()}
    y_pred = {s: np.zeros(n, dtype=int) for s, n in n_per_sensor.items()}

    for ep in episodes:
        y_true[ep["sensor_id"]][ep["start_idx"]: ep["end_idx"] + 1] = 1

    parsed = []

    for event in events:

        p = event["payload"]
        sensor = p["sensor_id"]

        if sensor not in n_per_sensor:
            continue

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

    events = [e for e in events if e["payload"]["sensor_id"] in n_per_sensor]

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


def run_once(
    readings,
    scores,
    episodes,
    model,
    min_flagged,
    tuner_on,
    n_per_sensor,
    percentile=PERCENTILE,
):

    tuner = SignificanceThresholdTuner(
        model.calibration_scores, percentile=percentile
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
            "percentile": percentile,
            "dropped_candidates": detector.dropped_candidates,
            "flagged_readings": processor.flagged_count,
            "threshold_start": threshold_start,
            "threshold_end": tuner.threshold,
            "tuner_adaptations": state["adaptations"],
            "tuner_freezes": state["freezes"],
        }
    )

    return metrics, processor, publisher


def _n_per_sensor(readings):

    counts = {}

    for r in readings:
        counts[r["sensor_id"]] = counts.get(r["sensor_id"], 0) + 1

    return counts


def _scores(model, readings):

    X = np.array([[r[f] for f in FEATURES] for r in readings])

    return model.score_batch(X)


def _numeric(metrics):

    return {
        k: float(v)
        for k, v in metrics.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


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
    parser.add_argument("--extra-percentile", type=float, default=None)
    args = parser.parse_args(argv)

    readings, episodes = build_stream()
    n_per_sensor = _n_per_sensor(readings)

    results_dir.mkdir(parents=True, exist_ok=True)

    if args.events_file:

        with open(args.events_file, encoding="utf-8") as handle:
            events = [json.loads(line) for line in handle if line.strip()]

        metrics = evaluate_events(events, episodes, n_per_sensor)

        print("REAL RUN (events from Kafka consumer, de-duplicated on episode_id)")
        frame = _print_table([_row("real", None, "tuner on", metrics)])
        frame.to_csv(results_dir / "real_run_eval.csv", index=False)

        print("\nwritten: results/real_run_eval.csv")

        return

    import mlflow

    model = load_stream_model()
    scores = _scores(model, readings)

    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT)

    rows = []
    kind_rows = []
    extra_row = None
    heldout_row = None

    with mlflow.start_run(run_name="stream-eval"):

        mlflow.log_params(
            {
                "percentile": PERCENTILE,
                "gap_minutes": GAP.total_seconds() / 60,
                "severe_margin": SEVERE_MARGIN,
                "miss_cost": MISS_COST,
                "false_alarm_cost": FALSE_ALARM_COST,
                "model_version": model.version,
            }
        )

        for label, min_flagged, tuner_on in RUNS:

            metrics, _, _ = run_once(
                readings, scores, episodes, model, min_flagged, tuner_on, n_per_sensor
            )

            with mlflow.start_run(run_name=f"run-{label}", nested=True):
                mlflow.log_params(
                    {"min_flagged_readings": min_flagged, "tuner_on": tuner_on}
                )
                mlflow.log_metrics(_numeric(metrics))

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

        # Held-out patterns: run B settings, reporting only.
        held_readings, held_episodes = build_stream(
            seed=STREAM_SEED + 100,
            kinds={**EPISODE_KINDS, **HELDOUT_KINDS},
            kind_order=HELDOUT_ORDER,
        )
        held_n = _n_per_sensor(held_readings)
        held_scores = _scores(model, held_readings)

        held_metrics, _, _ = run_once(
            held_readings, held_scores, held_episodes, model, 2, True, held_n
        )

        heldout_row = _row("heldout-B", 2, "tuner on", held_metrics)

        for kind, (detected, total) in held_metrics["by_kind"].items():
            heldout_row[f"detected_{kind}"] = detected
            heldout_row[f"total_{kind}"] = total

        with mlflow.start_run(run_name="heldout-B", nested=True):
            mlflow.log_params({"min_flagged_readings": 2, "tuner_on": True})
            mlflow.log_metrics(_numeric(held_metrics))

        # Optional run E: percentile chosen on a SEPARATE tuning stream.
        if args.extra_percentile:

            extra_metrics, _, _ = run_once(
                readings,
                scores,
                episodes,
                model,
                2,
                False,
                n_per_sensor,
                percentile=args.extra_percentile,
            )

            extra_row = _row(
                "E", 2, f"frozen p{args.extra_percentile}", extra_metrics
            )

            with mlflow.start_run(run_name="run-E", nested=True):
                mlflow.log_params(
                    {"min_flagged_readings": 2, "percentile": args.extra_percentile}
                )
                mlflow.log_metrics(_numeric(extra_metrics))

        print(
            f"seeds: train/calibration/stream differ; percentile={PERCENTILE}; "
            f"gap={GAP}; severe_margin={SEVERE_MARGIN}; model={model.version}"
        )

        frame = _print_table(rows)

        kinds = pd.DataFrame(kind_rows)
        kinds["recall"] = kinds["detected"] / kinds["total"]

        print()
        print(
            kinds.pivot(index="kind", columns="run", values="recall")
            .round(3)
            .to_string()
        )

        print("\nHELD-OUT PATTERNS (run B settings, not used for any design choice)")
        held_frame = _print_table([heldout_row])

        frame.to_csv(results_dir / "stream_eval_results.csv", index=False)
        kinds.to_csv(results_dir / "stream_eval_by_kind.csv", index=False)
        held_frame.to_csv(results_dir / "stream_eval_heldout.csv", index=False)

        written = [
            "stream_eval_results.csv",
            "stream_eval_by_kind.csv",
            "stream_eval_heldout.csv",
        ]

        if extra_row is not None:
            print("\nRUN E (percentile chosen on a separate tuning stream)")
            extra_frame = _print_table([extra_row])
            extra_frame.to_csv(results_dir / "stream_eval_extra.csv", index=False)
            written.append("stream_eval_extra.csv")

        for name in written:
            mlflow.log_artifact(str(results_dir / name))

    print("\nwritten: " + ", ".join(f"results/{n}" for n in written))


if __name__ == "__main__":
    main()