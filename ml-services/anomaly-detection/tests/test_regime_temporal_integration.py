from pathlib import Path

import numpy as np
import pandas as pd

from src.model_loader import (
    feature_names,
    get_models,
)

from src.regime_detector import (
    RegimeDetector,
)


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)

OUTPUT_DIR = (
    PROJECT_ROOT / "output"
)

CALIBRATION = (
    OUTPUT_DIR / "calibration_normal.csv"
)

SEASONAL = (
    OUTPUT_DIR / "test_seasonal_normal.csv"
)

DRIFT = (
    OUTPUT_DIR / "test_temperature_drift.csv"
)


# ============================================================
# General detector configuration
# ============================================================

BASELINE_SIZE = 100

CANDIDATE_SIZES = [
    10,
    25,
    50,
    100,
    200,
]

MIN_STABLE_BLOCKS = 2

PERCENTILE = 99.0


# ============================================================
# MODEL-SPECIFIC REGIME CONFIGURATION
#
# These values come from the model-specific regime
# calibration performed earlier.
# ============================================================

MODEL_REGIME_CONFIG = {
    "iforest": {
        "shift_sigma": 1.50,
        "stability_tolerance": 0.20,
    },

    "lof": {
        "shift_sigma": 2.50,
        "stability_tolerance": 0.30,
    },

    "ocsvm": {
        "shift_sigma": 2.25,
        "stability_tolerance": 0.20,
    },
}


# ============================================================
# Score calculation
# ============================================================

def get_scores(
    df,
    model,
):
    """
    Project anomaly-score convention.

    Higher score = more anomalous.
    """

    X = df[
        feature_names
    ].to_numpy()

    scores = -model.score(
        X
    )

    return np.asarray(
        scores,
        dtype=float,
    )


# ============================================================
# Threshold
# ============================================================

def calculate_threshold(
    scores,
):
    """
    Calculate the P99 threshold from
    confirmed regime scores.
    """

    scores = np.asarray(
        scores,
        dtype=float,
    )

    if len(scores) == 0:
        return None

    return float(
        np.percentile(
            scores,
            PERCENTILE,
        )
    )


# ============================================================
# Test one model
# ============================================================

def test_model(
    model_name,
    model,
    calibration_df,
    seasonal_df,
    drift_df,
):
    print()
    print("=" * 80)

    print(
        f"{model_name.upper()} "
        "— SEASONAL → REGIME → DRIFT"
    )

    print("=" * 80)

    # --------------------------------------------------------
    # Model-specific configuration
    # --------------------------------------------------------

    if model_name not in MODEL_REGIME_CONFIG:
        raise AssertionError(
            f"No regime configuration defined "
            f"for model '{model_name}'."
        )

    config = MODEL_REGIME_CONFIG[
        model_name
    ]

    shift_sigma = float(
        config["shift_sigma"]
    )

    stability_tolerance = float(
        config["stability_tolerance"]
    )

    print()
    print(
        "MODEL REGIME CONFIGURATION"
    )

    print("-" * 80)

    print(
        f"Shift sigma         : "
        f"{shift_sigma:.2f}"
    )

    print(
        f"Stability tolerance : "
        f"{stability_tolerance:.2f}"
    )

    print(
        f"Minimum stable blocks: "
        f"{MIN_STABLE_BLOCKS}"
    )

    # --------------------------------------------------------
    # Scores
    # --------------------------------------------------------

    calibration_scores = get_scores(
        calibration_df,
        model,
    )

    seasonal_scores = get_scores(
        seasonal_df,
        model,
    )

    drift_scores = get_scores(
        drift_df,
        model,
    )

    # --------------------------------------------------------
    # Initialize regime detector
    # --------------------------------------------------------

    detector = RegimeDetector(
        baseline_size=BASELINE_SIZE,
        candidate_sizes=CANDIDATE_SIZES,
        shift_sigma=shift_sigma,
        stability_tolerance=(
            stability_tolerance
        ),
        min_stable_blocks=(
            MIN_STABLE_BLOCKS
        ),
    )

    detector.initialize(
        calibration_scores
    )

    # ========================================================
    # PHASE 1
    #
    # Original normal regime
    # ========================================================

    print()
    print(
        "PHASE 1 — ORIGINAL REGIME"
    )

    print("-" * 80)

    original_triggered = False

    for score in calibration_scores:

        result = detector.observe(
            score
        )

        if result[
            "regime_confirmed"
        ]:

            original_triggered = True
            break

    print(
        f"Regime incorrectly confirmed : "
        f"{original_triggered}"
    )

    assert not original_triggered, (
        f"{model_name}: original normal "
        "data incorrectly triggered a regime."
    )

    # --------------------------------------------------------
    # Reset before seasonal experiment
    # --------------------------------------------------------

    detector.reset()

    detector.initialize(
        calibration_scores
    )

    # ========================================================
    # PHASE 2
    #
    # Seasonal shift
    # ========================================================

    print()
    print(
        "PHASE 2 — SEASONAL SHIFT"
    )

    print("-" * 80)

    confirmation_index = None

    for index, score in enumerate(
        seasonal_scores
    ):

        result = detector.observe(
            score
        )

        if result[
            "regime_confirmed"
        ]:

            confirmation_index = index
            break

    print(
        f"Regime confirmed : "
        f"{confirmation_index is not None}"
    )

    print(
        f"Confirmation index : "
        f"{confirmation_index}"
    )

    confirmed_scores = np.asarray(
        detector.get_confirmed_scores(),
        dtype=float,
    )

    print(
        f"Confirmed samples : "
        f"{len(confirmed_scores)}"
    )

    assert (
        confirmation_index is not None
    ), (
        f"{model_name}: seasonal "
        "regime was not confirmed."
    )

    assert (
        len(confirmed_scores) == 200
    ), (
        f"{model_name}: expected "
        "200 confirmed samples."
    )

    # ========================================================
    # Establish new regime threshold
    # ========================================================

    threshold = calculate_threshold(
        confirmed_scores
    )

    assert threshold is not None

    print()
    print(
        f"New regime P99 threshold : "
        f"{threshold:.6f}"
    )

    # ========================================================
    # PHASE 3
    #
    # Continued seasonal operation
    # ========================================================

    print()
    print(
        "PHASE 3 — CONTINUED SEASONAL OPERATION"
    )

    print("-" * 80)

    remaining_start = (
        confirmation_index + 1
    )

    remaining_seasonal_scores = (
        seasonal_scores[
            remaining_start:
        ]
    )

    seasonal_false_positives = int(
        np.sum(
            remaining_seasonal_scores
            > threshold
        )
    )

    seasonal_total = len(
        remaining_seasonal_scores
    )

    seasonal_fpr = (
        seasonal_false_positives
        / seasonal_total
        if seasonal_total
        else 0.0
    )

    print(
        f"Remaining samples : "
        f"{seasonal_total}"
    )

    print(
        f"False positives    : "
        f"{seasonal_false_positives}"
    )

    print(
        f"False positive rate: "
        f"{seasonal_fpr:.4f}"
    )

    assert (
        seasonal_fpr < 0.05
    ), (
        f"{model_name}: seasonal regime "
        "still produces excessive false positives."
    )

    # ========================================================
    # PHASE 4
    #
    # Slow temperature drift
    # ========================================================

    print()
    print(
        "PHASE 4 — SLOW TEMPERATURE DRIFT"
    )

    print("-" * 80)

    drift_above_threshold = (
        drift_scores
        > threshold
    )

    drift_detected = int(
        np.sum(
            drift_above_threshold
        )
    )

    drift_total = len(
        drift_scores
    )

    drift_detection_rate = (
        drift_detected
        / drift_total
        if drift_total
        else 0.0
    )

    print(
        f"Drift samples     : "
        f"{drift_total}"
    )

    print(
        f"Above threshold   : "
        f"{drift_detected}"
    )

    print(
        f"Detection rate     : "
        f"{drift_detection_rate:.4f}"
    )

    # ========================================================
    # Drift score trend
    # ========================================================

    midpoint = (
        len(drift_scores) // 2
    )

    first_half = (
        drift_scores[:midpoint]
    )

    second_half = (
        drift_scores[midpoint:]
    )

    first_mean = float(
        np.mean(first_half)
    )

    second_mean = float(
        np.mean(second_half)
    )

    score_increase = (
        second_mean
        - first_mean
    )

    print()
    print(
        "DRIFT SCORE TREND"
    )

    print("-" * 80)

    print(
        f"First half mean score  : "
        f"{first_mean:.6f}"
    )

    print(
        f"Second half mean score : "
        f"{second_mean:.6f}"
    )

    print(
        f"Score increase         : "
        f"{score_increase:.6f}"
    )

    assert (
        second_mean > first_mean
    ), (
        f"{model_name}: drift did not "
        "produce an increasing model-score pattern."
    )

    # ========================================================
    # Final detector state
    # ========================================================

    state = detector.get_state()

    print()
    print(
        "FINAL REGIME STATE"
    )

    print("-" * 80)

    print(
        state
    )

    print()
    print(
        "[PASS] Seasonal regime was confirmed, "
        "seasonal operation remained stable, "
        "and drift produced a measurable "
        "score trend."
    )


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 80)

    print(
        "R4 REGIME + TEMPORAL BEHAVIOR INTEGRATION"
    )

    print("=" * 80)

    print()
    print(
        "MODEL-SPECIFIC REGIME CONFIGURATION"
    )

    print("-" * 80)

    for model_name, config in (
        MODEL_REGIME_CONFIG.items()
    ):

        print(
            f"{model_name:<10} "
            f"sigma={config['shift_sigma']:.2f} "
            f"tolerance="
            f"{config['stability_tolerance']:.2f}"
        )

    # --------------------------------------------------------
    # Validate datasets
    # --------------------------------------------------------

    required_files = [
        CALIBRATION,
        SEASONAL,
        DRIFT,
    ]

    for path in required_files:

        if not path.exists():
            raise FileNotFoundError(
                f"Required dataset not found: {path}"
            )

    # --------------------------------------------------------
    # Load datasets
    # --------------------------------------------------------

    calibration_df = pd.read_csv(
        CALIBRATION
    )

    seasonal_df = pd.read_csv(
        SEASONAL
    )

    drift_df = pd.read_csv(
        DRIFT
    )

    print()
    print(
        f"Calibration samples : "
        f"{len(calibration_df)}"
    )

    print(
        f"Seasonal samples    : "
        f"{len(seasonal_df)}"
    )

    print(
        f"Drift samples       : "
        f"{len(drift_df)}"
    )

    # --------------------------------------------------------
    # Models
    # --------------------------------------------------------

    models = get_models()

    supported_models = [
        name
        for name in models
        if name in MODEL_REGIME_CONFIG
    ]

    assert set(
        supported_models
    ) == set(
        MODEL_REGIME_CONFIG
    ), (
        "Mismatch between loaded models "
        "and MODEL_REGIME_CONFIG."
    )

    # --------------------------------------------------------
    # Run every model
    # --------------------------------------------------------

    for model_name in (
        "iforest",
        "lof",
        "ocsvm",
    ):

        if model_name not in models:
            raise ValueError(
                f"Required model '{model_name}' "
                "is not available."
            )

        test_model(
            model_name,
            models[model_name],
            calibration_df,
            seasonal_df,
            drift_df,
        )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    print()
    print("=" * 80)

    print(
        "R4 REGIME + TEMPORAL BEHAVIOR "
        "INTEGRATION PASSED"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()