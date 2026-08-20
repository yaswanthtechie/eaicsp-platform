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
    OUTPUT_DIR / "calibration_normal.csv"
)

SEASONAL = (
    OUTPUT_DIR / "test_seasonal_normal.csv"
)

SPIKES = (
    OUTPUT_DIR / "test_temperature_spike.csv"
)

DRIFT = (
    OUTPUT_DIR / "test_temperature_drift.csv"
)


# ============================================================
# R4 configuration
# ============================================================

BASELINE_SIZE = 100

CANDIDATE_SIZES = [
    10,
    25,
    50,
    100,
    200,
]

SHIFT_SIGMA = 2.0

STABILITY_TOLERANCE = 0.20

MIN_STABLE_BLOCKS = 2

PERCENTILE = 99.0


# ============================================================
# Score helper
# ============================================================

def get_scores(
    df,
    model,
):
    """
    Project score convention.

    Higher score = more anomalous.
    """

    X = df[
        feature_names
    ].to_numpy()

    return np.asarray(
        -model.score(X),
        dtype=float,
    )


# ============================================================
# Metrics
# ============================================================

def calculate_metrics(
    y_true,
    predictions,
):
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
# Regime detection
# ============================================================

def detect_seasonal_regime(
    calibration_scores,
    seasonal_scores,
):
    """
    Feed the seasonal data sequentially into the regime
    detector.

    The detector starts with the original calibration regime.

    It must explicitly confirm the new stable regime before
    threshold recalibration occurs.
    """

    detector = RegimeDetector(
        baseline_size=BASELINE_SIZE,
        candidate_sizes=CANDIDATE_SIZES,
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
        ):

            confirmation_index = index

            break

    confirmed_scores = np.asarray(
        detector.get_confirmed_scores(),
        dtype=float,
    )

    return (
        detector,
        confirmation_index,
        confirmed_scores,
    )


# ============================================================
# Threshold calibration
# ============================================================

def calibrate_threshold(
    confirmed_scores,
):
    """
    Calculate a new threshold ONLY after a regime has been
    confirmed.

    No rolling update is used here.
    """

    if len(confirmed_scores) == 0:

        return None

    return float(
        np.percentile(
            confirmed_scores,
            PERCENTILE,
        )
    )


# ============================================================
# Evaluate dataset
# ============================================================

def evaluate(
    df,
    scores,
    threshold,
):
    """
    Apply the newly calibrated regime threshold to a dataset.
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
    title,
    metrics,
):
    print()
    print(title)
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
        f"Precision : {metrics['precision']:.4f}"
    )

    print(
        f"Recall    : {metrics['recall']:.4f}"
    )

    print(
        f"F1        : {metrics['f1']:.4f}"
    )


# ============================================================
# Main model test
# ============================================================

def test_model(
    model_name,
    model,
    calibration_df,
    seasonal_df,
    spikes_df,
    drift_df,
):
    print()
    print("=" * 80)

    print(
        f"{model_name.upper()} "
        "— R4 REGIME + THRESHOLD INTEGRATION"
    )

    print("=" * 80)

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

    spikes_scores = get_scores(
        spikes_df,
        model,
    )

    drift_scores = get_scores(
        drift_df,
        model,
    )

    # --------------------------------------------------------
    # Establish new regime
    # --------------------------------------------------------

    (
        detector,
        confirmation_index,
        confirmed_scores,
    ) = detect_seasonal_regime(
        calibration_scores,
        seasonal_scores,
    )

    print()
    print(
        "REGIME DETECTION"
    )

    print("-" * 80)

    print(
        f"Confirmed          : "
        f"{confirmation_index is not None}"
    )

    print(
        f"Confirmation index : "
        f"{confirmation_index}"
    )

    print(
        f"Confirmed samples  : "
        f"{len(confirmed_scores)}"
    )

    if confirmation_index is None:

        print()
        print(
            "[FAIL] Seasonal regime "
            "was not confirmed."
        )

        return False

    # --------------------------------------------------------
    # New threshold
    # --------------------------------------------------------

    threshold = calibrate_threshold(
        confirmed_scores
    )

    print(
        f"New P99 threshold  : "
        f"{threshold:.6f}"
    )

    # --------------------------------------------------------
    # Evaluate ORIGINAL calibration
    # --------------------------------------------------------

    calibration_result = evaluate(
        calibration_df,
        calibration_scores,
        threshold,
    )

    print_metrics(
        "1. ORIGINAL CALIBRATION",
        calibration_result,
    )

    # --------------------------------------------------------
    # Evaluate seasonal normal
    # --------------------------------------------------------

    seasonal_result = evaluate(
        seasonal_df,
        seasonal_scores,
        threshold,
    )

    print_metrics(
        "2. SEASONAL NORMAL",
        seasonal_result,
    )

    # --------------------------------------------------------
    # Evaluate temperature spikes
    # --------------------------------------------------------

    spikes_result = evaluate(
        spikes_df,
        spikes_scores,
        threshold,
    )

    print_metrics(
        "3. TEMPERATURE SPIKES",
        spikes_result,
    )

    # --------------------------------------------------------
    # Evaluate temperature drift
    # --------------------------------------------------------

    drift_result = evaluate(
        drift_df,
        drift_scores,
        threshold,
    )

    print_metrics(
        "4. TEMPERATURE DRIFT",
        drift_result,
    )

    # --------------------------------------------------------
    # Interpretation
    # --------------------------------------------------------

    print()
    print(
        "R4 INTERPRETATION"
    )

    print("-" * 80)

    print(
        f"Seasonal false positives : "
        f"{seasonal_result['FP']}"
    )

    print(
        f"Spike TP                 : "
        f"{spikes_result['TP']}"
    )

    print(
        f"Spike FN                 : "
        f"{spikes_result['FN']}"
    )

    print(
        f"Drift TP                 : "
        f"{drift_result['TP']}"
    )

    print(
        f"Drift FN                 : "
        f"{drift_result['FN']}"
    )

    # --------------------------------------------------------
    # Basic assertions
    # --------------------------------------------------------

    assert (
        confirmation_index is not None
    ), (
        f"{model_name}: "
        "seasonal regime was not confirmed."
    )

    assert (
        len(confirmed_scores)
        == 200
    ), (
        f"{model_name}: expected "
        "200 confirmed regime samples."
    )

    assert (
        seasonal_result["FP"]
        < 200
    ), (
        f"{model_name}: seasonal false "
        "positives remain too high."
    )

    assert (
        spikes_result["TP"]
        >= 18
    ), (
        f"{model_name}: spike detection "
        "dropped below acceptable level."
    )

    print()
    print(
        "[PASS] Regime detection and "
        "threshold recalibration completed."
    )

    return True


# ============================================================
# Entry point
# ============================================================

def main():

    print("=" * 80)

    print(
        "R4 REGIME + THRESHOLD INTEGRATION TEST"
    )

    print("=" * 80)

    print()

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

    print(
        f"Calibration samples : "
        f"{len(calibration_df)}"
    )

    print(
        f"Seasonal samples    : "
        f"{len(seasonal_df)}"
    )

    print(
        f"Spike samples       : "
        f"{len(spikes_df)}"
    )

    print(
        f"Drift samples       : "
        f"{len(drift_df)}"
    )

    print()

    models = get_models()

    for model_name, model in models.items():

        test_model(
            model_name,
            model,
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