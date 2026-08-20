from pathlib import Path

import numpy as np
import pandas as pd

from src.temporal_detector import TemporalDetector


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"

NORMAL = OUTPUT_DIR / "test_normal.csv"
SEASONAL = OUTPUT_DIR / "test_seasonal_normal.csv"
SPIKES = OUTPUT_DIR / "test_temperature_spike.csv"
DRIFT = OUTPUT_DIR / "test_temperature_drift.csv"


# ============================================================
# Configuration
# ============================================================

WINDOW_SIZE = 24
MIN_SLOPE = 0.03
MIN_TOTAL_CHANGE = 0.75
MIN_R_SQUARED = 0.15

# Require three consecutive qualifying trend evaluations.
#
# This is temporal persistence.
#
# The detector should not react to a single noisy window.
REQUIRED_CONSECUTIVE_WINDOWS = 3

# Maximum acceptable confirmation latency.
#
# This is intentionally measured in readings, not in percentage
# of drift rows detected.
#
# At 5-minute sampling:
#
#     72 readings = 6 hours
#
# The injected drift lasts substantially longer than this.
MAX_DRIFT_CONFIRMATION_LATENCY = 72


# ============================================================
# Detector factory
# ============================================================

def create_detector():
    return TemporalDetector(
        window_size=WINDOW_SIZE,
        min_slope=MIN_SLOPE,
        min_total_change=MIN_TOTAL_CHANGE,
        min_r_squared=MIN_R_SQUARED,
        required_consecutive_windows=(
            REQUIRED_CONSECUTIVE_WINDOWS
        ),
    )


# ============================================================
# Run detector
# ============================================================

def run_detector(df):
    detector = create_detector()

    results = []

    for temperature in df["temperature"].to_numpy():

        result = detector.update(
            temperature
        )

        results.append(result)

    return detector, results


# ============================================================
# Summary
# ============================================================

def summarize(
    name,
    results,
):
    drift_flags = np.array(
        [
            result["is_drift"]
            for result in results
        ],
        dtype=bool,
    )

    detected = int(
        drift_flags.sum()
    )

    total = len(results)

    flag_rate = (
        detected / total
        if total > 0
        else 0.0
    )

    print()
    print(name)
    print("-" * 70)

    print(
        f"Samples             : "
        f"{total}"
    )

    print(
        f"Drift confirmations : "
        f"{detected}"
    )

    print(
        f"Confirmation rate   : "
        f"{flag_rate:.4f}"
    )

    usable_results = [
        result
        for result in results
        if result["sample_count"]
        >= WINDOW_SIZE
    ]

    if usable_results:

        last = usable_results[-1]

        print(
            f"Final slope         : "
            f"{last['slope']:.6f}"
        )

        print(
            f"Final total change  : "
            f"{last['total_change']:.6f}"
        )

        print(
            f"Final R-squared     : "
            f"{last['r_squared']:.4f}"
        )

        print(
            f"Final direction     : "
            f"{last['direction']}"
        )

        print(
            f"Final trend windows : "
            f"{last['consecutive_trend_windows']}"
        )

    return detected, flag_rate


# ============================================================
# 1. Original normal
# ============================================================

def test_original_normal():

    print()
    print("=" * 80)
    print("1. ORIGINAL NORMAL")
    print("=" * 80)

    df = pd.read_csv(
        NORMAL
    )

    _, results = run_detector(
        df
    )

    detected, flag_rate = summarize(
        "ORIGINAL NORMAL",
        results,
    )

    # Original normal data should not produce sustained drift.
    assert flag_rate < 0.01, (
        "Temporal detector is producing "
        "too many false drift confirmations "
        "on original normal data."
    )

    print(
        "[PASS] Original normal data "
        "does not produce excessive "
        "sustained drift confirmations."
    )


# ============================================================
# 2. Seasonal normal
# ============================================================

def test_seasonal_normal():

    print()
    print("=" * 80)
    print("2. SEASONAL NORMAL")
    print("=" * 80)

    df = pd.read_csv(
        SEASONAL
    )

    _, results = run_detector(
        df
    )

    detected, flag_rate = summarize(
        "SEASONAL NORMAL",
        results,
    )

    assert flag_rate < 0.01, (
        "Temporal detector is producing "
        "too many sustained drift confirmations "
        "on seasonal normal data."
    )

    print(
        "[PASS] Seasonal normal data "
        "does not produce excessive "
        "sustained drift confirmations."
    )


# ============================================================
# 3. Temperature spikes
# ============================================================

def test_temperature_spikes():

    print()
    print("=" * 80)
    print("3. TEMPERATURE SPIKES")
    print("=" * 80)

    df = pd.read_csv(
        SPIKES
    )

    _, results = run_detector(
        df
    )

    detected, flag_rate = summarize(
        "TEMPERATURE SPIKES",
        results,
    )

    assert flag_rate < 0.01, (
        "Temporal detector is treating "
        "too many sudden temperature spikes "
        "as sustained drift."
    )

    print(
        "[PASS] Sudden temperature spikes "
        "are not broadly classified "
        "as sustained drift."
    )


# ============================================================
# 4. Slow temperature drift
# ============================================================

def test_temperature_drift():

    print()
    print("=" * 80)
    print("4. SLOW TEMPERATURE DRIFT")
    print("=" * 80)

    df = pd.read_csv(
        DRIFT
    )

    detector = create_detector()

    temperatures = (
        df["temperature"]
        .to_numpy()
    )

    labels = (
        df["is_anomaly"]
        .astype(int)
        .to_numpy()
    )

    results = []

    for temperature in temperatures:

        results.append(
            detector.update(
                temperature
            )
        )

    # --------------------------------------------------------
    # Locate injected drift
    # --------------------------------------------------------

    anomaly_indices = np.where(
        labels == 1
    )[0]

    assert len(
        anomaly_indices
    ) > 0, (
        "Temperature drift dataset "
        "contains no injected drift."
    )

    drift_start = int(
        anomaly_indices[0]
    )

    drift_end = int(
        anomaly_indices[-1]
    )

    drift_rows = len(
        anomaly_indices
    )

    print()
    print("DRIFT LOCATION")
    print("-" * 70)

    print(
        f"Start index : "
        f"{drift_start}"
    )

    print(
        f"End index   : "
        f"{drift_end}"
    )

    print(
        f"Drift rows  : "
        f"{drift_rows}"
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # We do NOT expect every drift row to be flagged.
    #
    # The detector needs historical evidence before it can
    # conclude that a sustained trend exists.
    #
    # Therefore we measure:
    #
    #     1. Whether drift is eventually confirmed
    #     2. Confirmation index
    #     3. Confirmation latency
    #
    # rather than:
    #
    #     detected drift rows / total drift rows
    # --------------------------------------------------------

    confirmations = [
        index
        for index, result in enumerate(results)
        if result["is_drift"]
    ]

    # --------------------------------------------------------
    # Any confirmation before the actual injected drift is a
    # false temporal confirmation.
    # --------------------------------------------------------

    pre_drift_confirmations = [
        index
        for index in confirmations
        if index < drift_start
    ]

    print()
    print("PRE-DRIFT CHECK")
    print("-" * 70)

    print(
        f"Drift confirmations before "
        f"drift start : "
        f"{len(pre_drift_confirmations)}"
    )

    assert len(
        pre_drift_confirmations
    ) == 0, (
        "Temporal detector confirmed "
        "drift before the injected "
        "temperature drift began."
    )

    # --------------------------------------------------------
    # Find first confirmation during the injected drift.
    # --------------------------------------------------------

    drift_confirmations = [
        index
        for index in confirmations
        if drift_start
        <= index
        <= drift_end
    ]

    print()
    print("DRIFT CONFIRMATION")
    print("-" * 70)

    if not drift_confirmations:

        print(
            "Drift confirmed : NO"
        )

        print(
            "[FAIL] Sustained temperature "
            "drift was never confirmed."
        )

        raise AssertionError(
            "Temporal detector failed to "
            "confirm the injected sustained "
            "temperature drift."
        )

    first_confirmation = int(
        drift_confirmations[0]
    )

    confirmation_latency = (
        first_confirmation
        - drift_start
    )

    print(
        "Drift confirmed : YES"
    )

    print(
        f"First confirmation index : "
        f"{first_confirmation}"
    )

    print(
        f"Confirmation latency     : "
        f"{confirmation_latency} readings"
    )

    print(
        f"Confirmation latency     : "
        f"{confirmation_latency * 5} minutes"
    )

    # --------------------------------------------------------
    # The detector should confirm within a reasonable period
    # after enough evidence becomes available.
    # --------------------------------------------------------

    assert (
        confirmation_latency
        <= MAX_DRIFT_CONFIRMATION_LATENCY
    ), (
        "Temporal detector eventually "
        "detected the drift, but confirmation "
        "latency is too large."
    )

    # --------------------------------------------------------
    # Strongest signal during injected drift
    # --------------------------------------------------------

    drift_results = [
        results[index]
        for index in range(
            drift_start,
            drift_end + 1,
        )
        if results[index]["sample_count"]
        >= WINDOW_SIZE
    ]

    if drift_results:

        strongest = max(
            drift_results,
            key=lambda result: (
                abs(result["slope"])
            )
        )

        print()
        print(
            "STRONGEST DRIFT SIGNAL"
        )

        print("-" * 70)

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
            f"Direction            : "
            f"{strongest['direction']}"
        )

        print(
            f"Consecutive windows  : "
            f"{strongest['consecutive_trend_windows']}"
        )

    print(
        "[PASS] Temporal detector confirmed "
        "the sustained temperature drift "
        "after accumulating sufficient evidence."
    )


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 80)

    print(
        "TEMPORAL TEMPERATURE DRIFT DETECTOR TEST"
    )

    print("=" * 80)

    print()

    print(
        "CONFIGURATION"
    )

    print("-" * 80)

    print(
        f"Window size                    : "
        f"{WINDOW_SIZE}"
    )

    print(
        f"Minimum slope                  : "
        f"{MIN_SLOPE}"
    )

    print(
        f"Minimum total change           : "
        f"{MIN_TOTAL_CHANGE}°C"
    )

    print(
        f"Minimum R-squared              : "
        f"{MIN_R_SQUARED}"
    )

    print(
        f"Required consecutive windows   : "
        f"{REQUIRED_CONSECUTIVE_WINDOWS}"
    )

    print(
        f"Maximum confirmation latency   : "
        f"{MAX_DRIFT_CONFIRMATION_LATENCY} "
        f"readings"
    )

    print()

    test_original_normal()

    test_seasonal_normal()

    test_temperature_spikes()

    test_temperature_drift()

    print()
    print("=" * 80)

    print(
        "ALL TEMPORAL DETECTOR TESTS PASSED"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()