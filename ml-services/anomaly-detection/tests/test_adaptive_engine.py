from pathlib import Path

import numpy as np
import pandas as pd

from src.adaptive_engine import AdaptiveEngine


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"

CALIBRATION = OUTPUT_DIR / "calibration_normal.csv"
SEASONAL = OUTPUT_DIR / "test_seasonal_normal.csv"
SPIKES = OUTPUT_DIR / "test_temperature_spike.csv"
DRIFT = OUTPUT_DIR / "test_temperature_drift.csv"


def load_dataset(path):
    df = pd.read_csv(path)

    required = {
        "temperature",
        "humidity",
        "stock_count",
        "is_anomaly",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"{path} missing columns: {sorted(missing)}"
        )

    return df


def load_model_scores(df, model_name):
    """
    Generate anomaly scores directly from the already-loaded
    project model.

    Higher score = more anomalous.
    """

    from src.model_loader import get_models, feature_names

    models = get_models()

    if model_name not in models:
        raise ValueError(
            f"Unknown model: {model_name}"
        )

    model = models[model_name]

    features = df[
        feature_names
    ].to_numpy(dtype=float)

    raw_scores = model.score(features)

    return -np.asarray(
        raw_scores,
        dtype=float,
    ).reshape(-1)


def metrics(
    scores,
    labels,
    threshold,
):
    predictions = scores > threshold

    labels = np.asarray(
        labels,
        dtype=int,
    )

    tp = int(
        np.sum(
            predictions
            & (labels == 1)
        )
    )

    tn = int(
        np.sum(
            (~predictions)
            & (labels == 0)
        )
    )

    fp = int(
        np.sum(
            predictions
            & (labels == 0)
        )
    )

    fn = int(
        np.sum(
            (~predictions)
            & (labels == 1)
        )
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

    fpr = (
        fp / (fp + tn)
        if fp + tn
        else 0.0
    )

    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fpr,
    }


def print_metrics(
    title,
    result,
):
    print()
    print(title)
    print("-" * 80)

    print(
        f"TP        : {result['tp']}"
    )

    print(
        f"TN        : {result['tn']}"
    )

    print(
        f"FP        : {result['fp']}"
    )

    print(
        f"FN        : {result['fn']}"
    )

    print(
        f"FPR       : {result['fpr']:.4f}"
    )

    print(
        f"Precision : {result['precision']:.4f}"
    )

    print(
        f"Recall    : {result['recall']:.4f}"
    )

    print(
        f"F1        : {result['f1']:.4f}"
    )


def run_stream(
    engine,
    df,
    scores,
):
    """
    Process a complete dataset through the engine.
    """

    results = []

    for index, row in df.iterrows():

        result = engine.process(
            score=float(
                scores[index]
            ),
            temperature=float(
                row["temperature"]
            ),
        )

        results.append(
            result
        )

    return results


def count_adaptations(results):
    return sum(
        bool(result["adapted"])
        for result in results
    )


def count_alerts(results):
    return sum(
        bool(result["alert"])
        for result in results
    )


def count_confirmations(results):
    return sum(
        bool(result["regime_confirmed"])
        and result["state"] == "stable"
        for result in results
    )


# ============================================================
# TEST 1
# ============================================================

def test_normal_operation(
    calibration_df,
    calibration_scores,
    model_name,
):
    print()
    print("=" * 80)
    print("TEST 1 — ORIGINAL NORMAL OPERATION")
    print("=" * 80)

    engine = AdaptiveEngine()

    engine.initialize(
        calibration_scores,
        model_name=model_name,
    )

    results = run_stream(
        engine,
        calibration_df,
        calibration_scores,
    )

    adaptations = count_adaptations(
        results
    )

    alerts = count_alerts(
        results
    )

    final_threshold = (
        engine.adaptive_threshold
        .get_threshold()
    )

    print(
        f"Adaptation updates : {adaptations}"
    )

    print(
        f"Alerts             : {alerts}"
    )

    print(
        f"Final threshold    : "
        f"{final_threshold:.6f}"
    )

    assert alerts == 0, (
        "Original calibration unexpectedly "
        "produced temporal drift alerts."
    )

    print(
        "[PASS] Original normal operation "
        "does not generate drift alerts."
    )

    return engine


# ============================================================
# TEST 2
# ============================================================

def test_seasonal_transition(
    calibration_df,
    calibration_scores,
    seasonal_df,
    seasonal_scores,
    model_name,
):
    print()
    print("=" * 80)
    print("TEST 2 — SEASONAL REGIME TRANSITION")
    print("=" * 80)

    engine = AdaptiveEngine()

    engine.initialize(
        calibration_scores,
        model_name=model_name,
    )

    initial_threshold = (
        engine.adaptive_threshold
        .get_threshold()
    )

    results = run_stream(
        engine,
        seasonal_df,
        seasonal_scores,
    )

    states = [
        result["state"]
        for result in results
    ]

    transition_count = states.count(
        "regime_confirmation"
    )

    drift_alerts = sum(
        result["alert"]
        for result in results
    )

    confirmations = sum(
        result["regime_confirmed"]
        for result in results
    )

    final_threshold = (
        engine.adaptive_threshold
        .get_threshold()
    )

    print(
        f"Initial threshold       : "
        f"{initial_threshold:.6f}"
    )

    print(
        f"Final threshold         : "
        f"{final_threshold:.6f}"
    )

    print(
        f"Confirmation states     : "
        f"{transition_count}"
    )

    print(
        f"Regime confirmations    : "
        f"{confirmations}"
    )

    print(
        f"Temporal drift alerts   : "
        f"{drift_alerts}"
    )

    # We mainly care that the regime machinery actually
    # enters transition/confirmation rather than blindly
    # adapting immediately.

    assert transition_count > 0, (
        "Seasonal data never entered regime confirmation."
    )

    print(
        "[PASS] Seasonal data entered the "
        "regime-transition path."
    )

    return (
        engine,
        results,
    )


# ============================================================
# TEST 3
# ============================================================

def test_drift_blocks_adaptation(
    calibration_scores,
    drift_df,
    drift_scores,
    model_name,
):
    print()
    print("=" * 80)
    print("TEST 3 — TEMPERATURE DRIFT BLOCKS ADAPTATION")
    print("=" * 80)

    engine = AdaptiveEngine()

    engine.initialize(
        calibration_scores,
        model_name=model_name,
    )

    initial_threshold = (
        engine.adaptive_threshold
        .get_threshold()
    )

    results = run_stream(
        engine,
        drift_df,
        drift_scores,
    )

    drift_results = [
        result
        for result in results
        if result["temporal_drift"]
    ]

    alerts = sum(
        result["alert"]
        for result in results
    )

    drift_adaptations = sum(
        result["adapted"]
        for result in drift_results
    )

    final_threshold = (
        engine.adaptive_threshold
        .get_threshold()
    )

    print(
        f"Initial threshold       : "
        f"{initial_threshold:.6f}"
    )

    print(
        f"Final threshold         : "
        f"{final_threshold:.6f}"
    )

    print(
        f"Temporal drift readings : "
        f"{len(drift_results)}"
    )

    print(
        f"Alerts                  : "
        f"{alerts}"
    )

    print(
        f"Adaptations during drift: "
        f"{drift_adaptations}"
    )

    assert drift_adaptations == 0, (
        "Adaptive threshold was updated while "
        "temporal drift was detected."
    )

    print(
        "[PASS] Temporal drift does not contaminate "
        "the adaptive baseline."
    )

    return engine, results


# ============================================================
# TEST 4
# ============================================================

def test_spikes_are_not_temporal_drift(
    calibration_scores,
    spikes_df,
    spike_scores,
    model_name,
):
    print()
    print("=" * 80)
    print("TEST 4 — TEMPERATURE SPIKES")
    print("=" * 80)

    engine = AdaptiveEngine()

    engine.initialize(
        calibration_scores,
        model_name=model_name,
    )

    results = run_stream(
        engine,
        spikes_df,
        spike_scores,
    )

    temporal_drift_count = sum(
        result["temporal_drift"]
        for result in results
    )

    alerts = sum(
        result["alert"]
        for result in results
    )

    print(
        f"Temporal drift detections : "
        f"{temporal_drift_count}"
    )

    print(
        f"Alerts                    : "
        f"{alerts}"
    )

    # Spikes should not be broadly interpreted as sustained
    # temporal drift.

    rate = (
        temporal_drift_count
        / len(results)
    )

    print(
        f"Temporal drift rate       : "
        f"{rate:.4f}"
    )

    assert rate < 0.05, (
        "Temperature spikes are being "
        "classified as sustained temporal drift "
        "too frequently."
    )

    print(
        "[PASS] Temperature spikes are not "
        "broadly classified as temporal drift."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print(
        "ADAPTIVE ENGINE STATE-MACHINE INTEGRATION TEST"
    )
    print("=" * 80)

    print()
    print(
        "Architecture:"
    )

    print(
        "Regime change → Temporal drift check → "
        "Regime confirmation → Adaptive threshold"
    )

    print()
    print(
        "Adaptive threshold is frozen during "
        "regime transitions and temporal drift."
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

    for model_name in (
        "iforest",
        "lof",
        "ocsvm",
    ):

        print()
        print("#" * 80)
        print(
            f"MODEL: {model_name.upper()}"
        )
        print("#" * 80)

        print()
        print(
            "Generating model scores..."
        )

        calibration_scores = load_model_scores(
            calibration_df,
            model_name,
        )

        seasonal_scores = load_model_scores(
            seasonal_df,
            model_name,
        )

        spike_scores = load_model_scores(
            spikes_df,
            model_name,
        )

        drift_scores = load_model_scores(
            drift_df,
            model_name,
        )

        print(
            "Scores generated."
        )

        # ----------------------------------------------------
        # 1. Original normal
        # ----------------------------------------------------

        test_normal_operation(
            calibration_df,
            calibration_scores,
            model_name,
        )

        # ----------------------------------------------------
        # 2. Seasonal transition
        # ----------------------------------------------------

        seasonal_engine, seasonal_results = (
            test_seasonal_transition(
                calibration_df,
                calibration_scores,
                seasonal_df,
                seasonal_scores,
                model_name,
            )
        )

        # ----------------------------------------------------
        # 3. Temperature drift
        # ----------------------------------------------------

        drift_engine, drift_results = (
            test_drift_blocks_adaptation(
                calibration_scores,
                drift_df,
                drift_scores,
                model_name,
            )
        )

        # ----------------------------------------------------
        # 4. Temperature spikes
        # ----------------------------------------------------

        test_spikes_are_not_temporal_drift(
            calibration_scores,
            spikes_df,
            spike_scores,
            model_name,
        )

        print()
        print(
            f"[COMPLETED] {model_name.upper()}"
        )

        print()
        print(
            "FINAL ENGINE STATE"
        )
        print("-" * 80)

        state = (
            seasonal_engine.get_state()
        )

        print(
            f"State                 : "
            f"{state['state']}"
        )

        print(
            f"Adaptation updates    : "
            f"{state['adaptation_updates']}"
        )

        print(
            f"Alerts                : "
            f"{state['alert_count']}"
        )

        print(
            f"Regime confirmations  : "
            f"{state['regime_confirmation_count']}"
        )

    print()
    print("=" * 80)
    print(
        "ADAPTIVE ENGINE TEST COMPLETED"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()