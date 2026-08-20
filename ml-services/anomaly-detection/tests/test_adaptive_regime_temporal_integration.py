from pathlib import Path

import numpy as np
import pandas as pd

from src.adaptive_threshold import AdaptiveThreshold
from src.model_loader import feature_names, get_models
from src.regime_detector import RegimeDetector
from src.temporal_detector import TemporalDetector


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"

CALIBRATION = OUTPUT_DIR / "calibration_normal.csv"
SEASONAL = OUTPUT_DIR / "test_seasonal_normal.csv"
SPIKES = OUTPUT_DIR / "test_temperature_spike.csv"
DRIFT = OUTPUT_DIR / "test_temperature_drift.csv"

MODELS = [
    "iforest",
    "lof",
    "ocsvm",
]

# ------------------------------------------------------------
# Adaptive threshold
# ------------------------------------------------------------

ADAPTIVE_WINDOW = 50
ADAPTIVE_PERCENTILE = 99.0

# ------------------------------------------------------------
# Regime detector
# ------------------------------------------------------------

REGIME_BASELINE_SIZE = 100

REGIME_CANDIDATE_SIZES = [
    10,
    25,
    50,
    100,
    200,
]

REGIME_SHIFT_SIGMA = 2.0
REGIME_STABILITY_TOLERANCE = 0.2
REGIME_MIN_STABLE_BLOCKS = 2

# ------------------------------------------------------------
# Temporal detector
# ------------------------------------------------------------

TEMPORAL_WINDOW = 24
TEMPORAL_MIN_SLOPE = 0.03
TEMPORAL_MIN_TOTAL_CHANGE = 0.75
TEMPORAL_MIN_R_SQUARED = 0.15
TEMPORAL_REQUIRED_WINDOWS = 3


# ============================================================
# Dataset helpers
# ============================================================

def load_dataset(path):
    df = pd.read_csv(path)

    required = set(
        feature_names + ["is_anomaly"]
    )

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"{path} is missing columns: "
            f"{sorted(missing)}"
        )

    return df


# ============================================================
# Model scoring
# ============================================================

def score_dataset(df, model_name):
    """
    Generate the project's normalized anomaly score.

    raw model score:
        model.score(...)

    project anomaly score:
        -raw_score

    Higher anomaly score = more anomalous.
    """

    models = get_models()

    if model_name not in models:
        raise ValueError(
            f"Unknown model: {model_name}"
        )

    model = models[model_name]

    features = df[
        feature_names
    ].to_numpy(dtype=float)

    raw_scores = model.score(
        features
    )

    raw_scores = np.asarray(
        raw_scores,
        dtype=float,
    ).reshape(-1)

    return -raw_scores


# ============================================================
# Metrics
# ============================================================

def confusion_matrix(actual, predicted):

    actual = np.asarray(
        actual,
        dtype=int,
    )

    predicted = np.asarray(
        predicted,
        dtype=int,
    )

    tp = int(
        np.sum(
            (actual == 1)
            & (predicted == 1)
        )
    )

    tn = int(
        np.sum(
            (actual == 0)
            & (predicted == 0)
        )
    )

    fp = int(
        np.sum(
            (actual == 0)
            & (predicted == 1)
        )
    )

    fn = int(
        np.sum(
            (actual == 1)
            & (predicted == 0)
        )
    )

    return tp, tn, fp, fn


def print_metrics(
    name,
    actual,
    predicted,
):
    tp, tn, fp, fn = confusion_matrix(
        actual,
        predicted,
    )

    fpr = (
        fp / (fp + tn)
        if fp + tn
        else 0.0
    )

    precision = (
        tp / (tp + fp)
        if tp + fp
        else 0.0
    )

    recall = (
        tp / (tp + fn)
        if tp + fn
        else 0.0
    )

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if precision + recall
        else 0.0
    )

    print()
    print(name)
    print("-" * 80)
    print(f"TP        : {tp}")
    print(f"TN        : {tn}")
    print(f"FP        : {fp}")
    print(f"FN        : {fn}")
    print(f"FPR       : {fpr:.4f}")
    print(f"Precision : {precision:.4f}")
    print(f"Recall    : {recall:.4f}")
    print(f"F1        : {f1:.4f}")

    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "fpr": fpr,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


# ============================================================
# Regime detector factory
# ============================================================

def create_regime_detector():

    return RegimeDetector(
        baseline_size=REGIME_BASELINE_SIZE,
        candidate_sizes=REGIME_CANDIDATE_SIZES,
        shift_sigma=REGIME_SHIFT_SIGMA,
        stability_tolerance=REGIME_STABILITY_TOLERANCE,
        min_stable_blocks=REGIME_MIN_STABLE_BLOCKS,
    )


# ============================================================
# Regime detection
# ============================================================

def detect_regime(
    calibration_scores,
    seasonal_scores,
):
    """
    Run the existing RegimeDetector using its real API.

    Important:

        initialize(...)
        observe(...)
        is_confirmed()
        get_confirmed_scores()

    No artificial update/process API is introduced.
    """

    detector = create_regime_detector()

    detector.initialize(
        calibration_scores[
            :REGIME_BASELINE_SIZE
        ]
    )

    confirmation_index = None

    for index, score in enumerate(
        seasonal_scores
    ):

        detector.observe(
            float(score)
        )

        if detector.is_confirmed():

            confirmation_index = index
            break

    confirmed_scores = (
        detector.get_confirmed_scores()
    )

    confirmed_scores = np.asarray(
        confirmed_scores,
        dtype=float,
    )

    return (
        detector,
        confirmation_index,
        confirmed_scores,
    )


# ============================================================
# Main model test
# ============================================================

def run_model(
    model_name,
    calibration_df,
    seasonal_df,
    spikes_df,
    drift_df,
):

    print()
    print("=" * 80)
    print(
        f"{model_name.upper()} — "
        "FULL ADAPTIVE / REGIME / TEMPORAL INTEGRATION"
    )
    print("=" * 80)

    # ========================================================
    # Generate scores
    # ========================================================

    print()
    print(
        "Generating model scores..."
    )

    calibration_scores = score_dataset(
        calibration_df,
        model_name,
    )

    seasonal_scores = score_dataset(
        seasonal_df,
        model_name,
    )

    spike_scores = score_dataset(
        spikes_df,
        model_name,
    )

    drift_scores = score_dataset(
        drift_df,
        model_name,
    )

    print(
        "Scores generated."
    )

    # ========================================================
    # PHASE 1
    # Original calibration
    # ========================================================

    print()
    print(
        "PHASE 1 — ORIGINAL CALIBRATION"
    )
    print("-" * 80)

    adaptive = AdaptiveThreshold(
        window_size=ADAPTIVE_WINDOW,
        percentile=ADAPTIVE_PERCENTILE,
    )

    adaptive.initialize(
        calibration_scores
    )

    original_threshold = (
        adaptive.get_threshold()
    )

    print(
        f"Initial threshold : "
        f"{original_threshold:.6f}"
    )

    original_pred = (
        calibration_scores
        > original_threshold
    )

    print_metrics(
        "ORIGINAL CALIBRATION",
        calibration_df[
            "is_anomaly"
        ].to_numpy(),
        original_pred,
    )

    # ========================================================
    # PHASE 2
    # Regime detection
    # ========================================================

    print()
    print(
        "PHASE 2 — REGIME DETECTION"
    )
    print("-" * 80)

    (
        regime_detector,
        confirmation_index,
        confirmed_scores,
    ) = detect_regime(
        calibration_scores,
        seasonal_scores,
    )

    regime_state = (
        regime_detector.get_state()
    )

    print(
        f"Regime confirmed : "
        f"{regime_detector.is_confirmed()}"
    )

    print(
        f"Confirmation index : "
        f"{confirmation_index}"
    )

    print(
        f"Confirmed samples : "
        f"{len(confirmed_scores)}"
    )

    assert regime_detector.is_confirmed(), (
        f"{model_name}: "
        "seasonal regime was not confirmed."
    )

    assert len(
        confirmed_scores
    ) > 0, (
        f"{model_name}: "
        "no confirmed regime scores were returned."
    )

    # ========================================================
    # PHASE 3
    # Confirmed regime calibration
    # ========================================================

    print()
    print(
        "PHASE 3 — CONFIRMED REGIME CALIBRATION"
    )
    print("-" * 80)

    regime_threshold = float(
        np.percentile(
            confirmed_scores,
            ADAPTIVE_PERCENTILE,
        )
    )

    print(
        f"Original threshold : "
        f"{original_threshold:.6f}"
    )

    print(
        f"Regime threshold   : "
        f"{regime_threshold:.6f}"
    )

    print(
        f"Threshold movement : "
        f"{regime_threshold - original_threshold:.6f}"
    )

    # --------------------------------------------------------
    # Accept the confirmed regime using the detector's actual
    # API before moving forward.
    # --------------------------------------------------------

    regime_detector.accept_regime()

    # --------------------------------------------------------
    # Reinitialize adaptive threshold with the confirmed
    # regime.
    # --------------------------------------------------------

    adaptive.reset()

    adaptive.initialize(
        confirmed_scores
    )

    confirmed_threshold = (
        adaptive.get_threshold()
    )

    print(
        f"Adaptive threshold : "
        f"{confirmed_threshold:.6f}"
    )

    # ========================================================
    # PHASE 4
    # Continued seasonal operation
    # ========================================================

    print()
    print(
        "PHASE 4 — CONTINUED SEASONAL OPERATION"
    )
    print("-" * 80)

    start = (
        confirmation_index + 1
    )

    remaining_scores = (
        seasonal_scores[start:]
    )

    remaining_labels = (
        seasonal_df[
            "is_anomaly"
        ].to_numpy()[start:]
    )

    remaining_temperatures = (
        seasonal_df[
            "temperature"
        ].to_numpy()[start:]
    )

    temporal = TemporalDetector(
        window_size=TEMPORAL_WINDOW,
        min_slope=TEMPORAL_MIN_SLOPE,
        min_total_change=TEMPORAL_MIN_TOTAL_CHANGE,
        min_r_squared=TEMPORAL_MIN_R_SQUARED,
        required_consecutive_windows=(
            TEMPORAL_REQUIRED_WINDOWS
        ),
    )

    seasonal_predictions = []

    adaptive_updates = 0
    blocked_updates = 0

    for score, temperature in zip(
        remaining_scores,
        remaining_temperatures,
    ):

        temporal_result = temporal.update(
            float(temperature)
        )

        threshold = (
            adaptive.get_threshold()
        )

        is_anomaly = (
            float(score) > threshold
        )

        seasonal_predictions.append(
            is_anomaly
        )

        # ----------------------------------------------------
        # Only trusted normal readings update the baseline.
        #
        # Temporal drift blocks adaptation.
        # ----------------------------------------------------

        if (
            not is_anomaly
            and not temporal_result[
                "is_drift"
            ]
        ):

            adaptive.update(
                float(score)
            )

            adaptive_updates += 1

        else:

            blocked_updates += 1

    seasonal_predictions = np.asarray(
        seasonal_predictions,
        dtype=bool,
    )

    print(
        f"Remaining samples : "
        f"{len(remaining_scores)}"
    )

    print(
        f"Adaptive updates  : "
        f"{adaptive_updates}"
    )

    print(
        f"Blocked updates   : "
        f"{blocked_updates}"
    )

    seasonal_metrics = print_metrics(
        "CONTINUED SEASONAL NORMAL",
        remaining_labels,
        seasonal_predictions,
    )

    # ========================================================
    # PHASE 5
    # Temperature spikes
    # ========================================================

    print()
    print(
        "PHASE 5 — TEMPERATURE SPIKES"
    )
    print("-" * 80)

    temporal.reset()

    spike_predictions = []

    spike_adaptive_updates = 0
    spike_blocked_updates = 0

    for score, temperature in zip(
        spike_scores,
        spikes_df[
            "temperature"
        ].to_numpy(),
    ):

        temporal_result = temporal.update(
            float(temperature)
        )

        threshold = (
            adaptive.get_threshold()
        )

        is_anomaly = (
            float(score) > threshold
        )

        spike_predictions.append(
            is_anomaly
        )

        if (
            not is_anomaly
            and not temporal_result[
                "is_drift"
            ]
        ):

            adaptive.update(
                float(score)
            )

            spike_adaptive_updates += 1

        else:

            spike_blocked_updates += 1

    spike_predictions = np.asarray(
        spike_predictions,
        dtype=bool,
    )

    print(
        f"Adaptive updates : "
        f"{spike_adaptive_updates}"
    )

    print(
        f"Blocked updates  : "
        f"{spike_blocked_updates}"
    )

    spike_metrics = print_metrics(
        "TEMPERATURE SPIKES",
        spikes_df[
            "is_anomaly"
        ].to_numpy(),
        spike_predictions,
    )

    # ========================================================
    # PHASE 6
    # Slow temperature drift
    # ========================================================

    print()
    print(
        "PHASE 6 — SLOW TEMPERATURE DRIFT"
    )
    print("-" * 80)

    temporal.reset()

    drift_predictions = []

    drift_confirmed = False
    drift_confirmation_index = None

    for index, (
        score,
        temperature,
    ) in enumerate(
        zip(
            drift_scores,
            drift_df[
                "temperature"
            ].to_numpy(),
        )
    ):

        temporal_result = temporal.update(
            float(temperature)
        )

        threshold = (
            adaptive.get_threshold()
        )

        is_anomaly = (
            float(score) > threshold
        )

        drift_predictions.append(
            is_anomaly
        )

        # ----------------------------------------------------
        # Never adapt during confirmed temporal drift.
        # ----------------------------------------------------

        if (
            not is_anomaly
            and not temporal_result[
                "is_drift"
            ]
        ):

            adaptive.update(
                float(score)
            )

        if (
            temporal_result[
                "is_drift"
            ]
            and not drift_confirmed
        ):

            drift_confirmed = True

            drift_confirmation_index = (
                index
            )

    drift_predictions = np.asarray(
        drift_predictions,
        dtype=bool,
    )

    print(
        f"Temporal drift confirmed : "
        f"{drift_confirmed}"
    )

    print(
        f"Drift confirmation index : "
        f"{drift_confirmation_index}"
    )

    drift_metrics = print_metrics(
        "TEMPERATURE DRIFT",
        drift_df[
            "is_anomaly"
        ].to_numpy(),
        drift_predictions,
    )

    # ========================================================
    # FINAL STATE
    # ========================================================

    print()
    print(
        "FINAL ADAPTIVE STATE"
    )
    print("-" * 80)

    adaptive_state = (
        adaptive.get_state()
    )

    for key, value in (
        adaptive_state.items()
    ):

        print(
            f"{key:<25}: {value}"
        )

    print()
    print(
        "FINAL REGIME STATE"
    )
    print("-" * 80)

    final_regime_state = (
        regime_detector.get_state()
    )

    for key, value in (
        final_regime_state.items()
    ):

        print(
            f"{key:<25}: {value}"
        )

    # ========================================================
    # Assertions
    # ========================================================

    assert (
        confirmed_threshold is not None
    )

    assert (
        len(confirmed_scores)
        >= 100
    ), (
        f"{model_name}: "
        "confirmed regime is too small."
    )

    assert (
        spike_metrics["recall"]
        >= 0.80
    ), (
        f"{model_name}: "
        "too many temperature spikes "
        "were missed."
    )

    assert drift_confirmed, (
        f"{model_name}: "
        "temporal detector did not "
        "confirm temperature drift."
    )

    print()
    print(
        f"[PASS] {model_name} full integration "
        "completed."
    )


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 80)
    print(
        "ADAPTIVE + REGIME + TEMPORAL "
        "STREAMING INTEGRATION TEST"
    )
    print("=" * 80)

    print()
    print(
        "Lifecycle:"
    )

    print(
        "calibration → regime detection → "
        "confirmed regime calibration → "
        "adaptive operation"
    )

    print(
        "Temporal drift blocks adaptive "
        "baseline contamination."
    )

    calibration_df = load_dataset(
        CALIBRATION
    )

    seasonal_df = load_dataset(
        SEASONAL
    )

    spikes_df = load_dataset(
        SPIKES
    )

    drift_df = load_dataset(
        DRIFT
    )

    print()
    print(
        "DATASET SIZES"
    )
    print("-" * 80)

    print(
        f"Calibration : {len(calibration_df)}"
    )

    print(
        f"Seasonal    : {len(seasonal_df)}"
    )

    print(
        f"Spikes      : {len(spikes_df)}"
    )

    print(
        f"Drift       : {len(drift_df)}"
    )

    for model_name in MODELS:

        run_model(
            model_name,
            calibration_df,
            seasonal_df,
            spikes_df,
            drift_df,
        )

    print()
    print("=" * 80)
    print(
        "TEST COMPLETED"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()