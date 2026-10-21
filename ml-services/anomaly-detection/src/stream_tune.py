"""
Pick the threshold percentile on a SEPARATE tuning stream (never the
evaluation stream). Rule fixed in advance: lowest episode cost
(miss 500, false alarm 2), ties -> higher recall. Settings: min 2, frozen.

Run: python -m src.stream_tune
Then: python -m src.stream_eval --extra-percentile <chosen>
"""

import pandas as pd

from .stream_eval import _n_per_sensor, _scores, results_dir, run_once
from .stream_model import load_stream_model
from .stream_simulator import STREAM_SEED, build_stream

PERCENTILES = [95.0, 97.0, 98.0, 99.0, 99.5]
TUNE_SEED = STREAM_SEED + 10


def main():

    model = load_stream_model()
    readings, episodes = build_stream(seed=TUNE_SEED)
    n = _n_per_sensor(readings)
    scores = _scores(model, readings)

    rows = []

    for p in PERCENTILES:
        metrics, _, _ = run_once(
            readings, scores, episodes, model, 2, False, n, percentile=p
        )
        rows.append(
            {
                "percentile": p,
                "detected": metrics["detected"],
                "missed": metrics["missed"],
                "false_alarm_events": metrics["false_alarm_events"],
                "event_precision": metrics["event_precision"],
                "event_recall": metrics["event_recall"],
                "episode_cost": metrics["episode_cost"],
            }
        )

    frame = pd.DataFrame(rows)
    print(frame.round(4).to_string(index=False))

    best = frame.sort_values(
        ["episode_cost", "event_recall"], ascending=[True, False]
    ).iloc[0]

    print(f"\nchosen percentile (tuning stream seed {TUNE_SEED}): {best['percentile']}")

    results_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(results_dir / "stream_tuning_stream.csv", index=False)


if __name__ == "__main__":
    main()