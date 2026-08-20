from pathlib import Path

import pandas as pd

from src.temporal_detector import TemporalDetector


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DRIFT = PROJECT_ROOT / "output" / "test_temperature_drift.csv"


WINDOW_SIZE = 24
MIN_SLOPE = 0.03
MIN_TOTAL_CHANGE = 0.75
MIN_R_SQUARED = 0.15
REQUIRED_CONSECUTIVE_WINDOWS = 3


def main():

    print("=" * 80)
    print("TEMPORAL DRIFT EVIDENCE INSPECTION")
    print("=" * 80)

    df = pd.read_csv(DRIFT)

    drift_indices = df.index[
        df["is_anomaly"].astype(int) == 1
    ].to_numpy()

    if len(drift_indices) == 0:
        raise RuntimeError(
            "No injected drift found."
        )

    drift_start = int(drift_indices[0])
    drift_end = int(drift_indices[-1])

    print()
    print("DRIFT REGION")
    print("-" * 80)
    print(f"Start index : {drift_start}")
    print(f"End index   : {drift_end}")
    print(f"Rows        : {len(drift_indices)}")

    detector = TemporalDetector(
        window_size=WINDOW_SIZE,
        min_slope=MIN_SLOPE,
        min_total_change=MIN_TOTAL_CHANGE,
        min_r_squared=MIN_R_SQUARED,
        required_consecutive_windows=(
            REQUIRED_CONSECUTIVE_WINDOWS
        ),
    )

    results = []

    for temperature in df["temperature"].to_numpy():
        results.append(
            detector.update(temperature)
        )

    print()
    print("QUALIFYING WINDOWS AROUND DRIFT")
    print("-" * 80)

    print(
        f"{'Index':>8} "
        f"{'Slope':>10} "
        f"{'Change':>10} "
        f"{'R²':>8} "
        f"{'Trend':>8} "
        f"{'Consecutive':>12} "
        f"{'Drift':>8}"
    )

    print("-" * 80)

    # Inspect from shortly before drift through the end.
    start = max(
        WINDOW_SIZE,
        drift_start - 60,
    )

    end = min(
        len(results),
        drift_end + 1,
    )

    for index in range(start, end):

        result = results[index]

        if not result.get("evaluated", True):
            continue

        print(
            f"{index:8d} "
            f"{result['slope']:10.5f} "
            f"{result['total_change']:10.5f} "
            f"{result['r_squared']:8.4f} "
            f"{str(result['trend_detected']):>8} "
            f"{result['consecutive_trend_windows']:12d} "
            f"{str(result['is_drift']):>8}"
        )

    # --------------------------------------------------------
    # First confirmation
    # --------------------------------------------------------

    confirmations = [
        i
        for i, result in enumerate(results)
        if result["is_drift"]
    ]

    print()
    print("CONFIRMATION")
    print("-" * 80)

    if confirmations:

        first = confirmations[0]

        print(
            f"First confirmation : {first}"
        )

        print(
            f"Drift start        : {drift_start}"
        )

        print(
            f"Latency            : "
            f"{first - drift_start} readings"
        )

        print(
            f"Latency            : "
            f"{(first - drift_start) * 5} minutes"
        )

    else:

        print(
            "No drift confirmation."
        )

    # --------------------------------------------------------
    # Condition statistics
    # --------------------------------------------------------

    drift_window_results = [
        results[i]
        for i in range(
            drift_start,
            drift_end + 1,
        )
        if results[i].get(
            "evaluated",
            True,
        )
    ]

    if drift_window_results:

        slope_pass = sum(
            abs(r["slope"]) >= MIN_SLOPE
            for r in drift_window_results
        )

        change_pass = sum(
            abs(r["total_change"])
            >= MIN_TOTAL_CHANGE
            for r in drift_window_results
        )

        r2_pass = sum(
            r["r_squared"]
            >= MIN_R_SQUARED
            for r in drift_window_results
        )

        trend_pass = sum(
            r["trend_detected"]
            for r in drift_window_results
        )

        print()
        print("DRIFT CONDITION ANALYSIS")
        print("-" * 80)

        total = len(
            drift_window_results
        )

        print(
            f"Evaluated windows : {total}"
        )

        print(
            f"Slope condition   : "
            f"{slope_pass}/{total}"
        )

        print(
            f"Change condition  : "
            f"{change_pass}/{total}"
        )

        print(
            f"R² condition      : "
            f"{r2_pass}/{total}"
        )

        print(
            f"Trend qualified   : "
            f"{trend_pass}/{total}"
        )

    # --------------------------------------------------------
    # Strongest evidence
    # --------------------------------------------------------

    if drift_window_results:

        strongest = max(
            drift_window_results,
            key=lambda r: (
                abs(r["slope"])
                * max(r["r_squared"], 0.0)
            ),
        )

        print()
        print("STRONGEST EVIDENCE")
        print("-" * 80)

        print(
            f"Slope                : "
            f"{strongest['slope']:.6f}"
        )

        print(
            f"Total change         : "
            f"{strongest['total_change']:.6f}"
        )

        print(
            f"R-squared            : "
            f"{strongest['r_squared']:.4f}"
        )

        print(
            f"Trend detected       : "
            f"{strongest['trend_detected']}"
        )

        print(
            f"Consecutive windows  : "
            f"{strongest['consecutive_trend_windows']}"
        )

    print()
    print("=" * 80)
    print("INSPECTION COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()