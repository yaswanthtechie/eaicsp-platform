from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.metrics import (
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
)

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
    OUTPUT_DIR
    / "calibration_normal.csv"
)

SEASONAL = (
    OUTPUT_DIR
    / "test_seasonal_normal.csv"
)

SPIKES = (
    OUTPUT_DIR
    / "test_temperature_spike.csv"
)

DRIFT = (
    OUTPUT_DIR
    / "test_temperature_drift.csv"
)


# ============================================================
# Configuration
# ============================================================

BASELINE_SIZE = 100

REGIME_SIZES = [
    200,
    300,
]

SHIFT_SIGMA = 2.0

STABILITY_TOLERANCE = 0.20

MIN_STABLE_BLOCKS = 2

PERCENTILE = 99.0


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

    return -model.score(
        X
    )


# ============================================================
# Metrics
# ============================================================

def calculate_metrics(
    y_true,
    predictions,
):
    """
    Calculate confusion-matrix metrics.
    """

    tn, fp, fn, tp = (
        confusion_matrix(
            y_true,
            predictions,
            labels=[0, 1],
        ).ravel()
    )

    return {
        "TP": int(tp),
        "TN": int(tn),
        "FP": int(fp),
        "FN": int(fn),
        "precision": precision_score(
            y_true,
            predictions,
            zero_division=0,
        ),
        "recall": recall_score(
            y_true,
            predictions,
            zero_division=0,
        ),
        "f1": f1_score(
            y_true,
            predictions,
            zero_division=0,
        ),
    }


# ============================================================
# Regime detector
# ============================================================

def detect_regime(
    calibration_scores,
    seasonal_scores,
    regime_size,
):
    """
    Detect a stable seasonal regime.

    Candidate sizes progress up to the requested regime size.
    """

    candidate_sizes = [
        size
        for size in [
            10,
            25,
            50,
            100,
            200,
            300,
        ]
        if size <= regime_size
    ]

    detector = RegimeDetector(
        candidate_sizes=candidate_sizes,
        baseline_size=BASELINE_SIZE,
        shift_sigma=SHIFT_SIGMA,
        stability_tolerance=(
            STABILITY_TOLERANCE
        ),
        min_stable_blocks=(
            MIN_STABLE_BLOCKS
        ),
    )

    detector.initialize(
        calibration_scores
    )

    confirmation_index = None

    for index, score in enumerate(
        seasonal_scores
    ):

        result = detector.observe(
            score
        )

        if (
            result["regime_confirmed"]
            and confirmation_index is None
        ):

            confirmation_index = index

            break

    confirmed_scores = (
        detector.get_confirmed_scores()
    )

    return {
        "detector": detector,
        "confirmation_index": (
            confirmation_index
        ),
        "confirmed_scores": (
            np.asarray(
                confirmed_scores,
                dtype=float,
            )
        ),
    }


# ============================================================
# Threshold
# ============================================================

def calculate_threshold(
    scores,
):
    """
    Calculate the P99 threshold from the confirmed regime.

    This is deliberately separate from the detector.

    RegimeDetector answers:
        "Has the operating regime changed?"

    This function answers:
        "What score threshold represents the new regime?"
    """

    scores = np.asarray(
        scores,
        dtype=float,
    )

    scores = scores[
        np.isfinite(scores)
    ]

    if scores.size == 0:

        return None

    return float(
        np.percentile(
            scores,
            PERCENTILE,
        )
    )


# ============================================================
# Evaluate threshold
# ============================================================

def evaluate_threshold(
    threshold,
    df,
    scores,
):
    """
    Evaluate one threshold against one labeled dataset.
    """

    y_true = (
        df["is_anomaly"]
        .astype(int)
        .to_numpy()
    )

    predictions = (
        scores > threshold
    ).astype(int)

    return calculate_metrics(
        y_true,
        predictions,
    )


# ============================================================
# Print metrics
# ============================================================

def print_metrics(
    name,
    metrics,
):
    """
    Print confusion-matrix metrics.
    """

    print()
    print(
        name
    )

    print("-" * 70)

    print(
        f"TP        : {metrics['TP']}"
    )

    print(
        f"TN        : {metrics['TN']}"
    )

    print(
        f"FP        : {metrics['FP']}"
    )

    print(
        f"FN        : {metrics['FN']}"
    )

    print(
        f"Precision : "
        f"{metrics['precision']:.4f}"
    )

    print(
        f"Recall    : "
        f"{metrics['recall']:.4f}"
    )

    print(
        f"F1        : "
        f"{metrics['f1']:.4f}"
    )


# ============================================================
# Evaluate one regime size
# ============================================================

def evaluate_regime_size(
    model_name,
    model,
    calibration_df,
    seasonal_df,
    spikes_df,
    drift_df,
    regime_size,
):
    """
    Detect and calibrate a new seasonal regime, then evaluate
    that confirmed-regime threshold against all requested
    datasets.
    """

    calibration_scores = get_scores(
        calibration_df,
        model,
    )

    seasonal_scores = get_scores(
        seasonal_df,
        model,
    )

    spikes_scores = get_scores(
        spikes_df,
        model,
    )

    drift_scores = get_scores(
        drift_df,
        model,
    )

    detection = detect_regime(
        calibration_scores,
        seasonal_scores,
        regime_size,
    )

    confirmed_scores = (
        detection["confirmed_scores"]
    )

    threshold = calculate_threshold(
        confirmed_scores
    )

    print()
    print("=" * 80)

    print(
        f"{model_name.upper()} — "
        f"REGIME SIZE {regime_size}"
    )

    print("=" * 80)

    print()

    print(
        "REGIME DETECTION"
    )

    print("-" * 80)

    print(
        f"Confirmation index : "
        f"{detection['confirmation_index']}"
    )

    print(
        f"Confirmed samples  : "
        f"{len(confirmed_scores)}"
    )

    if threshold is None:

        print(
            "Threshold          : None"
        )

        print(
            "[FAIL] No confirmed "
            "regime threshold."
        )

        return None

    print(
        f"New P99 threshold  : "
        f"{threshold:.6f}"
    )

    # --------------------------------------------------------
    # Dataset evaluations
    # --------------------------------------------------------

    print()

    print(
        "CONFIRMED-REGIME THRESHOLD"
    )

    print("-" * 80)

    # Original calibration has no injected anomalies.
    calibration_result = (
        evaluate_threshold(
            threshold,
            calibration_df,
            calibration_scores,
        )
    )

    print_metrics(
        "1. ORIGINAL CALIBRATION",
        calibration_result,
    )

    # Seasonal normal should have no false positives ideally.
    seasonal_result = (
        evaluate_threshold(
            threshold,
            seasonal_df,
            seasonal_scores,
        )
    )

    print_metrics(
        "2. SEASONAL NORMAL",
        seasonal_result,
    )

    # Temperature spikes should remain detectable.
    spikes_result = (
        evaluate_threshold(
            threshold,
            spikes_df,
            spikes_scores,
        )
    )

    print_metrics(
        "3. TEMPERATURE SPIKES",
        spikes_result,
    )

    # Drift is intentionally labeled anomalous in the current
    # dataset. This tells us what the new seasonal calibration
    # does to the existing drift detector.
    drift_result = (
        evaluate_threshold(
            threshold,
            drift_df,
            drift_scores,
        )
    )

    print_metrics(
        "4. TEMPERATURE DRIFT",
        drift_result,
    )

    return {
        "model": model_name,
        "regime_size": regime_size,
        "confirmation_index": (
            detection["confirmation_index"]
        ),
        "confirmed_sample_count": (
            len(confirmed_scores)
        ),
        "threshold": threshold,
        "calibration": calibration_result,
        "seasonal": seasonal_result,
        "spikes": spikes_result,
        "drift": drift_result,
    }


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 80)

    print(
        "CONFIRMED REGIME CALIBRATION"
    )

    print("=" * 80)

    print()

    print(
        "Testing regime sizes:"
    )

    print(
        REGIME_SIZES
    )

    print()

    print(
        "Datasets:"
    )

    print(
        f"Calibration : "
        f"{CALIBRATION}"
    )

    print(
        f"Seasonal    : "
        f"{SEASONAL}"
    )

    print(
        f"Spikes      : "
        f"{SPIKES}"
    )

    print(
        f"Drift       : "
        f"{DRIFT}"
    )

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    calibration_df = pd.read_csv(
        CALIBRATION
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

    print()

    print(
        "DATASET SIZES"
    )

    print("-" * 80)

    print(
        f"Calibration : "
        f"{len(calibration_df)}"
    )

    print(
        f"Seasonal    : "
        f"{len(seasonal_df)}"
    )

    print(
        f"Spikes      : "
        f"{len(spikes_df)}"
    )

    print(
        f"Drift       : "
        f"{len(drift_df)}"
    )

    # --------------------------------------------------------
    # Evaluate every model and both regime sizes
    # --------------------------------------------------------

    models = get_models()

    all_results = []

    for model_name, model in models.items():

        for regime_size in REGIME_SIZES:

            result = evaluate_regime_size(
                model_name,
                model,
                calibration_df,
                seasonal_df,
                spikes_df,
                drift_df,
                regime_size,
            )

            if result is not None:

                all_results.append(
                    result
                )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 80)

    print(
        "SUMMARY — 200 VS 300"
    )

    print("=" * 80)

    print()

    print(
        "Model    Size   Confirm  Threshold    "
        "Seasonal FP  Spike TP/FN  Drift TP/FN"
    )

    print("-" * 80)

    for result in all_results:

        seasonal = (
            result["seasonal"]
        )

        spikes = (
            result["spikes"]
        )

        drift = (
            result["drift"]
        )

        print(
            f"{result['model']:8} "
            f"{result['regime_size']:4}   "
            f"{str(result['confirmation_index']):>6}   "
            f"{result['threshold']:10.6f}   "
            f"{seasonal['FP']:>8}     "
            f"{spikes['TP']:>2}/"
            f"{spikes['FN']:<2}       "
            f"{drift['TP']:>3}/"
            f"{drift['FN']:<3}"
        )

    print()
    print("=" * 80)

    print(
        "TEST COMPLETED"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()