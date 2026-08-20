from pathlib import Path

import numpy as np
import pandas as pd

from src.adaptive_threshold import AdaptiveThreshold
from src.model_loader import feature_names, get_models


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"

CALIBRATION = OUTPUT_DIR / "calibration_normal.csv"
SEASONAL = OUTPUT_DIR / "test_seasonal_normal.csv"
SPIKES = OUTPUT_DIR / "test_temperature_spike.csv"


MODELS = [
    "iforest",
    "lof",
    "ocsvm",
]


WINDOW_SIZES = [
    50,
    100,
    200,
]

PERCENTILE = 99.0


# ============================================================
# Dataset
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
# Score generation
# ============================================================

def score_dataset(
    df,
    model_name,
):

    models = get_models()

    if model_name not in models:
        raise ValueError(
            f"Unknown model: {model_name}"
        )

    model = models[
        model_name
    ]

    features = df[
        feature_names
    ].to_numpy(
        dtype=float
    )

    raw_scores = model.score(
        features
    )

    raw_scores = np.asarray(
        raw_scores,
        dtype=float,
    ).reshape(-1)

    # Project convention:
    #
    # raw score -> anomaly score
    #
    # Higher = more anomalous.

    return -raw_scores


# ============================================================
# Statistics
# ============================================================

def percentile(
    scores,
    value,
):

    return float(
        np.percentile(
            np.asarray(
                scores,
                dtype=float,
            ),
            value,
        )
    )


def describe(
    name,
    scores,
):

    scores = np.asarray(
        scores,
        dtype=float,
    )

    print()
    print(name)
    print("-" * 80)

    print(
        f"Samples : {len(scores)}"
    )

    print(
        f"Mean    : {np.mean(scores):.6f}"
    )

    print(
        f"Std     : {np.std(scores):.6f}"
    )

    print(
        f"P95     : "
        f"{percentile(scores, 95):.6f}"
    )

    print(
        f"P99     : "
        f"{percentile(scores, 99):.6f}"
    )

    print(
        f"Minimum : {np.min(scores):.6f}"
    )

    print(
        f"Maximum : {np.max(scores):.6f}"
    )


# ============================================================
# Test 1
#
# Calibration stability
# ============================================================

def test_calibration_stability(
    calibration_scores,
    model_name,
):

    print()
    print(
        "1. CALIBRATION STABILITY"
    )
    print("-" * 80)

    for window_size in WINDOW_SIZES:

        manager = AdaptiveThreshold(
            window_size=window_size,
            percentile=PERCENTILE,
        )

        manager.initialize(
            calibration_scores
        )

        initial = (
            manager.get_threshold()
        )

        thresholds = []

        for score in calibration_scores:

            manager.update(
                float(score)
            )

            thresholds.append(
                manager.get_threshold()
            )

        final = (
            manager.get_threshold()
        )

        movement = (
            final - initial
        )

        print()
        print(
            f"Window size : {window_size}"
        )

        print(
            f"Initial     : {initial:.6f}"
        )

        print(
            f"Final       : {final:.6f}"
        )

        print(
            f"Movement    : {movement:.6f}"
        )

        assert np.isfinite(
            final
        )

        print(
            "[PASS] Threshold remains finite."
        )


# ============================================================
# Test 2
#
# Seasonal adaptation
# ============================================================

def test_seasonal_adaptation(
    calibration_scores,
    seasonal_scores,
    model_name,
):

    print()
    print(
        "2. SEASONAL ADAPTATION"
    )
    print("-" * 80)

    for window_size in WINDOW_SIZES:

        manager = AdaptiveThreshold(
            window_size=window_size,
            percentile=PERCENTILE,
        )

        manager.initialize(
            calibration_scores
        )

        initial = (
            manager.get_threshold()
        )

        thresholds = []

        for score in seasonal_scores:

            manager.update(
                float(score)
            )

            thresholds.append(
                manager.get_threshold()
            )

        final = (
            manager.get_threshold()
        )

        seasonal_p99 = percentile(
            seasonal_scores,
            PERCENTILE,
        )

        print()
        print(
            f"Window size : {window_size}"
        )

        print(
            f"Initial threshold  : "
            f"{initial:.6f}"
        )

        print(
            f"Seasonal P99       : "
            f"{seasonal_p99:.6f}"
        )

        print(
            f"Final threshold    : "
            f"{final:.6f}"
        )

        print(
            f"Threshold movement : "
            f"{final - initial:.6f}"
        )

        if final < initial:

            print(
                "[WARNING] Threshold moved downward "
                "during seasonal adaptation."
            )

        else:

            print(
                "[PASS] Threshold did not collapse "
                "below its initial value."
            )


# ============================================================
# Test 3
#
# Spike contamination
# ============================================================

def test_spike_contamination(
    calibration_scores,
    spike_scores,
):

    print()
    print(
        "3. ANOMALY CONTAMINATION TEST"
    )
    print("-" * 80)

    manager = AdaptiveThreshold(
        window_size=50,
        percentile=PERCENTILE,
    )

    manager.initialize(
        calibration_scores
    )

    initial = (
        manager.get_threshold()
    )

    print(
        f"Initial threshold : "
        f"{initial:.6f}"
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # This test intentionally feeds ONLY trusted-normal
    # scores into update().
    #
    # We first determine which spike readings would be
    # considered anomalous by the initial threshold.
    # Those readings are NOT allowed into the adaptive
    # baseline.
    # --------------------------------------------------------

    accepted = 0
    rejected = 0

    predictions = []

    for score in spike_scores:

        is_anomaly = (
            score > initial
        )

        predictions.append(
            is_anomaly
        )

        if not is_anomaly:

            manager.update(
                float(score)
            )

            accepted += 1

        else:

            rejected += 1

    final = (
        manager.get_threshold()
    )

    print(
        f"Spike samples      : "
        f"{len(spike_scores)}"
    )

    print(
        f"Accepted as normal : "
        f"{accepted}"
    )

    print(
        f"Rejected anomalies  : "
        f"{rejected}"
    )

    print(
        f"Initial threshold  : "
        f"{initial:.6f}"
    )

    print(
        f"Final threshold    : "
        f"{final:.6f}"
    )

    print(
        f"Movement           : "
        f"{final - initial:.6f}"
    )

    assert np.isfinite(
        final
    )

    print(
        "[PASS] Adaptive threshold "
        "remained numerically valid."
    )


# ============================================================
# Test 4
#
# Trusted-normal-only contamination experiment
# ============================================================

def test_trusted_normal_contamination(
    calibration_scores,
    seasonal_scores,
):

    print()
    print(
        "4. TRUSTED-NORMAL CONTAMINATION EXPERIMENT"
    )
    print("-" * 80)

    manager = AdaptiveThreshold(
        window_size=50,
        percentile=PERCENTILE,
    )

    manager.initialize(
        calibration_scores
    )

    initial = (
        manager.get_threshold()
    )

    accepted_scores = []

    for score in seasonal_scores:

        current_threshold = (
            manager.get_threshold()
        )

        # Simulate the current integration policy:
        #
        # below threshold = trusted normal

        if score <= current_threshold:

            manager.update(
                float(score)
            )

            accepted_scores.append(
                float(score)
            )

    final = (
        manager.get_threshold()
    )

    print(
        f"Initial threshold : "
        f"{initial:.6f}"
    )

    print(
        f"Final threshold   : "
        f"{final:.6f}"
    )

    print(
        f"Movement          : "
        f"{final - initial:.6f}"
    )

    print(
        f"Accepted scores   : "
        f"{len(accepted_scores)}"
    )

    if accepted_scores:

        print(
            f"Accepted P99      : "
            f"{percentile(accepted_scores, 99):.6f}"
        )

        print(
            f"Accepted minimum  : "
            f"{np.min(accepted_scores):.6f}"
        )

        print(
            f"Accepted maximum  : "
            f"{np.max(accepted_scores):.6f}"
        )

    if final < initial:

        print()
        print(
            "[IMPORTANT] The current rule "
            "'score <= threshold = trusted normal' "
            "allows the adaptive threshold to move "
            "downward."
        )

        print(
            "This is evidence that the integration "
            "policy needs an additional trust condition."
        )

    else:

        print(
            "[PASS] No downward threshold collapse "
            "observed in this experiment."
        )


# ============================================================
# Model test
# ============================================================

def run_model(
    model_name,
    calibration_df,
    seasonal_df,
    spike_df,
):

    print()
    print("=" * 80)
    print(
        f"{model_name.upper()} — "
        "ADAPTIVE THRESHOLD STABILITY"
    )
    print("=" * 80)

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
        spike_df,
        model_name,
    )

    print(
        "Scores generated."
    )

    describe(
        "CALIBRATION SCORES",
        calibration_scores,
    )

    describe(
        "SEASONAL SCORES",
        seasonal_scores,
    )

    describe(
        "SPIKE SCORES",
        spike_scores,
    )

    test_calibration_stability(
        calibration_scores,
        model_name,
    )

    test_seasonal_adaptation(
        calibration_scores,
        seasonal_scores,
        model_name,
    )

    test_spike_contamination(
        calibration_scores,
        spike_scores,
    )

    test_trusted_normal_contamination(
        calibration_scores,
        seasonal_scores,
    )

    print()
    print(
        f"[COMPLETED] {model_name}"
    )


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 80)
    print(
        "ADAPTIVE THRESHOLD STABILITY / "
        "CONTAMINATION TEST"
    )
    print("=" * 80)

    print()
    print(
        "Purpose:"
    )

    print(
        "Determine whether the adaptive threshold itself "
        "becomes unstable when trusted-normal scores are "
        "fed into its rolling baseline."
    )

    print()
    print(
        "This test does NOT modify AdaptiveThreshold."
    )

    print(
        "It is diagnostic and is intended to determine "
        "the correct integration policy."
    )

    calibration_df = load_dataset(
        CALIBRATION
    )

    seasonal_df = load_dataset(
        SEASONAL
    )

    spike_df = load_dataset(
        SPIKES
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
        f"{len(spike_df)}"
    )

    for model_name in MODELS:

        run_model(
            model_name,
            calibration_df,
            seasonal_df,
            spike_df,
        )

    print()
    print("=" * 80)
    print(
        "TEST COMPLETED"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()