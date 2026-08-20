from pathlib import Path

import numpy as np
import pandas as pd

from src.adaptive_engine import AdaptiveEngine


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

CALIBRATION = OUT / "calibration_normal.csv"
SEASONAL = OUT / "test_seasonal_normal.csv"


def scores(df, model_name):
    from src.model_loader import get_models, feature_names

    model = get_models()[model_name]

    X = df[feature_names].to_numpy(dtype=float)

    return -np.asarray(
        model.score(X),
        dtype=float,
    ).reshape(-1)


def main():

    model_name = "iforest"

    calibration = pd.read_csv(
        CALIBRATION
    )

    seasonal = pd.read_csv(
        SEASONAL
    )

    calibration_scores = scores(
        calibration,
        model_name,
    )

    seasonal_scores = scores(
        seasonal,
        model_name,
    )

    engine = AdaptiveEngine(
        baseline_size=100,
        candidate_sizes=[
            10,
            25,
            50,
            100,
            200,
        ],
        shift_sigma=2.0,
        stability_tolerance=0.2,
        min_stable_blocks=2,
        adaptive_window_size=50,
        adaptive_percentile=99.0,
    )

    engine.initialize(
        calibration_scores
    )

    print("=" * 80)
    print(
        "INSPECT ADAPTIVE SEASONAL ALERTS"
    )
    print("=" * 80)

    print(
        "\nPHASE 1 — FIRST SEASONAL PASS"
    )

    first = []

    for i in range(len(seasonal)):

        result = engine.process(
            score=float(
                seasonal_scores[i]
            ),
            temperature=float(
                seasonal.iloc[i]["temperature"]
            ),
        )

        first.append(result)

    threshold = (
        engine.adaptive_threshold.get_threshold()
    )

    print(
        f"Threshold after first pass : "
        f"{threshold:.9f}"
    )

    print(
        "\nPHASE 2 — SECOND SEASONAL PASS"
    )

    alerts = []

    for i in range(len(seasonal)):

        result = engine.process(
            score=float(
                seasonal_scores[i]
            ),
            temperature=float(
                seasonal.iloc[i]["temperature"]
            ),
        )

        if result["alert"]:

            alerts.append(
                (
                    i,
                    result,
                )
            )

    print(
        f"Total alerts : {len(alerts)}"
    )

    print()
    print(
        "ALERT DETAILS"
    )

    print("-" * 80)

    for index, result in alerts:

        print(
            f"Index={index:4d} "
            f"score={result['score']:.6f} "
            f"threshold={result['threshold']:.6f} "
            f"state={result['state']} "
            f"temporal_drift={result['temporal_drift']} "
            f"slope={result['slope']:.6f} "
            f"change={result['total_change']:.6f} "
            f"r2={result['r_squared']:.6f} "
            f"direction={result['direction']}"
        )

    print()
    print(
        "TEMPORAL ALERTS ONLY"
    )

    temporal = [
        item
        for item in alerts
        if item[1]["temporal_drift"]
    ]

    print(
        f"Temporal drift alerts : "
        f"{len(temporal)}"
    )

    print()
    print(
        "ADAPTATION"
    )

    adapted = [
        item
        for item in alerts
        if item[1]["adapted"]
    ]

    print(
        f"Alerts that adapted : "
        f"{len(adapted)}"
    )


if __name__ == "__main__":
    main()