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
# Established configuration
# ============================================================

WINDOW_SIZE = 24
MIN_SLOPE = 0.03
MIN_TOTAL_CHANGE = 0.75

REQUIRED_CONSECUTIVE_WINDOWS = 3

# Only this parameter is varied.
R_SQUARED_VALUES = [
    0.15,
    0.10,
    0.05,
]


# ============================================================
# Detector
# ============================================================

def create_detector(min_r_squared):
    return TemporalDetector(
        window_size=WINDOW_SIZE,
        min_slope=MIN_SLOPE,
        min_total_change=MIN_TOTAL_CHANGE,
        min_r_squared=min_r_squared,
        required_consecutive_windows=(
            REQUIRED_CONSECUTIVE_WINDOWS
        ),
    )


# ============================================================
# Run detector
# ============================================================

def run_detector(df, min_r_squared):

    detector = create_detector(
        min_r_squared
    )

    results = []

    for temperature in (
        df["temperature"].to_numpy()
    ):
        results.append(
            detector.update(
                temperature
            )
        )

    return results


# ============================================================
# Dataset statistics
# ============================================================

def evaluate_dataset(
    df,
    min_r_squared,
):

    results = run_detector(
        df,
        min_r_squared,
    )

    confirmations = [
        index
        for index, result in enumerate(results)
        if result["is_drift"]
    ]

    return results, confirmations


# ============================================================
# Print result
# ============================================================

def print_dataset_result(
    name,
    confirmations,
    total_samples,
):

    confirmation_count = len(
        confirmations
    )

    confirmation_rate = (
        confirmation_count
        / total_samples
        if total_samples > 0
        else 0.0
    )

    print(
        f"{name:<20}"
        f"{confirmation_count:>10}"
        f"{confirmation_rate:>14.4f}"
    )


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 80)
    print(
        "TEMPORAL R-SQUARED THRESHOLD SENSITIVITY"
    )
    print("=" * 80)

    print()
    print(
        "Only the minimum R-squared threshold is varied."
    )

    print(
        "Slope, total change, window size and persistence "
        "remain unchanged."
    )

    print()
    print(
        f"Window size                  : {WINDOW_SIZE}"
    )

    print(
        f"Minimum slope                : {MIN_SLOPE}"
    )

    print(
        f"Minimum total change         : "
        f"{MIN_TOTAL_CHANGE}°C"
    )

    print(
        f"Required consecutive windows : "
        f"{REQUIRED_CONSECUTIVE_WINDOWS}"
    )

    print(
        f"R-squared values tested      : "
        f"{R_SQUARED_VALUES}"
    )

    # --------------------------------------------------------
    # Load datasets
    # --------------------------------------------------------

    normal_df = pd.read_csv(
        NORMAL
    )

    seasonal_df = pd.read_csv(
        SEASONAL
    )

    spikes_df = pd.read_csv(
        SPIKES
    )

    drift_df = pd.read_csv(
        DRIFT
    )

    # --------------------------------------------------------
    # Locate injected drift
    # --------------------------------------------------------

    drift_labels = (
        drift_df["is_anomaly"]
        .astype(int)
        .to_numpy()
    )

    drift_indices = np.where(
        drift_labels == 1
    )[0]

    if len(drift_indices) == 0:
        raise RuntimeError(
            "Temperature drift dataset "
            "contains no injected drift."
        )

    drift_start = int(
        drift_indices[0]
    )

    drift_end = int(
        drift_indices[-1]
    )

    print()
    print("=" * 80)
    print("DATASET INFORMATION")
    print("=" * 80)

    print()
    print(
        f"Normal samples   : "
        f"{len(normal_df)}"
    )

    print(
        f"Seasonal samples : "
        f"{len(seasonal_df)}"
    )

    print(
        f"Spike samples    : "
        f"{len(spikes_df)}"
    )

    print(
        f"Drift samples    : "
        f"{len(drift_df)}"
    )

    print(
        f"Drift start      : "
        f"{drift_start}"
    )

    print(
        f"Drift end        : "
        f"{drift_end}"
    )

    # --------------------------------------------------------
    # Results
    # --------------------------------------------------------

    all_results = {}

    # --------------------------------------------------------
    # Test every R² threshold
    # --------------------------------------------------------

    for r_squared in R_SQUARED_VALUES:

        print()
        print("=" * 80)

        print(
            f"R-SQUARED THRESHOLD = "
            f"{r_squared:.2f}"
        )

        print("=" * 80)

        # ----------------------------------------------------
        # Normal
        # ----------------------------------------------------

        normal_results, normal_confirmations = (
            evaluate_dataset(
                normal_df,
                r_squared,
            )
        )

        # ----------------------------------------------------
        # Seasonal
        # ----------------------------------------------------

        seasonal_results, seasonal_confirmations = (
            evaluate_dataset(
                seasonal_df,
                r_squared,
            )
        )

        # ----------------------------------------------------
        # Spikes
        # ----------------------------------------------------

        spike_results, spike_confirmations = (
            evaluate_dataset(
                spikes_df,
                r_squared,
            )
        )

        # ----------------------------------------------------
        # Drift
        # ----------------------------------------------------

        drift_results, drift_confirmations = (
            evaluate_dataset(
                drift_df,
                r_squared,
            )
        )

        # ----------------------------------------------------
        # Drift confirmation
        #
        # We care about the FIRST confirmation after the
        # injected drift starts.
        # ----------------------------------------------------

        pre_drift_confirmations = [
            index
            for index in drift_confirmations
            if index < drift_start
        ]

        during_drift_confirmations = [
            index
            for index in drift_confirmations
            if (
                drift_start
                <= index
                <= drift_end
            )
        ]

        first_confirmation = (
            during_drift_confirmations[0]
            if during_drift_confirmations
            else None
        )

        if first_confirmation is not None:

            latency = (
                first_confirmation
                - drift_start
            )

        else:

            latency = None

        # ----------------------------------------------------
        # Count qualifying windows inside drift
        #
        # This is diagnostic information. It tells us whether
        # lowering R² creates more usable evidence.
        # ----------------------------------------------------

        drift_window_results = [
            drift_results[index]
            for index in range(
                drift_start,
                drift_end + 1,
            )
            if drift_results[index].get(
                "evaluated",
                True,
            )
        ]

        qualifying_windows = sum(
            result["trend_detected"]
            for result in drift_window_results
        )

        # ----------------------------------------------------
        # Store
        # ----------------------------------------------------

        all_results[r_squared] = {
            "normal_confirmations": (
                normal_confirmations
            ),
            "seasonal_confirmations": (
                seasonal_confirmations
            ),
            "spike_confirmations": (
                spike_confirmations
            ),
            "drift_confirmations": (
                drift_confirmations
            ),
            "pre_drift_confirmations": (
                pre_drift_confirmations
            ),
            "during_drift_confirmations": (
                during_drift_confirmations
            ),
            "first_confirmation": (
                first_confirmation
            ),
            "latency": latency,
            "qualifying_windows": (
                qualifying_windows
            ),
        }

        # ----------------------------------------------------
        # Print
        # ----------------------------------------------------

        print()
        print(
            "CONFIRMATION SUMMARY"
        )

        print("-" * 80)

        print(
            f"{'Dataset':<20}"
            f"{'Confirmations':>14}"
            f"{'Rate':>14}"
        )

        print("-" * 80)

        print_dataset_result(
            "Original normal",
            normal_confirmations,
            len(normal_df),
        )

        print_dataset_result(
            "Seasonal normal",
            seasonal_confirmations,
            len(seasonal_df),
        )

        print_dataset_result(
            "Temperature spikes",
            spike_confirmations,
            len(spikes_df),
        )

        print_dataset_result(
            "Temperature drift",
            during_drift_confirmations,
            len(drift_df),
        )

        print()
        print(
            "DRIFT EVIDENCE"
        )

        print("-" * 80)

        print(
            f"Qualifying windows "
            f"inside drift : "
            f"{qualifying_windows}"
        )

        print(
            f"Pre-drift confirmations       : "
            f"{len(pre_drift_confirmations)}"
        )

        if first_confirmation is None:

            print(
                "First drift confirmation      : "
                "NONE"
            )

            print(
                "Confirmation latency          : "
                "N/A"
            )

        else:

            print(
                f"First drift confirmation      : "
                f"{first_confirmation}"
            )

            print(
                f"Confirmation latency          : "
                f"{latency} readings"
            )

            print(
                f"Confirmation latency          : "
                f"{latency * 5} minutes"
            )

    # ========================================================
    # Comparison
    # ========================================================

    print()
    print("=" * 80)
    print(
        "R-SQUARED COMPARISON"
    )
    print("=" * 80)

    print()

    print(
        f"{'R²':>6}"
        f"{'Normal':>12}"
        f"{'Seasonal':>12}"
        f"{'Spikes':>12}"
        f"{'Drift':>12}"
        f"{'Drift latency':>16}"
        f"{'Trend windows':>16}"
    )

    print("-" * 80)

    for r_squared in R_SQUARED_VALUES:

        result = all_results[
            r_squared
        ]

        latency = result[
            "latency"
        ]

        latency_text = (
            str(latency)
            if latency is not None
            else "N/A"
        )

        print(
            f"{r_squared:6.2f}"
            f"{len(result['normal_confirmations']):12d}"
            f"{len(result['seasonal_confirmations']):12d}"
            f"{len(result['spike_confirmations']):12d}"
            f"{len(result['during_drift_confirmations']):12d}"
            f"{latency_text:>16}"
            f"{result['qualifying_windows']:16d}"
        )

    # ========================================================
    # Interpretation
    # ========================================================

    print()
    print("=" * 80)
    print(
        "INTERPRETATION"
    )
    print("=" * 80)

    baseline = all_results[
        R_SQUARED_VALUES[0]
    ]

    print()

    print(
        "Baseline R² = "
        f"{R_SQUARED_VALUES[0]:.2f}"
    )

    print(
        f"Normal confirmations   : "
        f"{len(baseline['normal_confirmations'])}"
    )

    print(
        f"Seasonal confirmations : "
        f"{len(baseline['seasonal_confirmations'])}"
    )

    print(
        f"Spike confirmations    : "
        f"{len(baseline['spike_confirmations'])}"
    )

    if baseline["latency"] is not None:

        print(
            f"Drift latency          : "
            f"{baseline['latency']} readings"
        )

    else:

        print(
            "Drift latency          : "
            "NOT CONFIRMED"
        )

    print()
    print(
        "Lower R² should only be considered "
        "if it improves drift confirmation "
        "without introducing sustained false "
        "drift confirmations on normal, "
        "seasonal, or spike data."
    )

    print()
    print("=" * 80)
    print(
        "TEST COMPLETED"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()