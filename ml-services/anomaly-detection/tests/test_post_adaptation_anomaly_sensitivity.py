from pathlib import Path

import numpy as np
import pandas as pd

from src.adaptive_engine import AdaptiveEngine


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"

CALIBRATION = OUTPUT_DIR / "calibration_normal.csv"
SEASONAL = OUTPUT_DIR / "test_seasonal_normal.csv"
SPIKES = OUTPUT_DIR / "test_temperature_spike.csv"


MODELS = (
    "iforest",
    "lof",
    "ocsvm",
)


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


def get_scores(df, model_name):
    from src.model_loader import (
        get_models,
        feature_names,
    )

    models = get_models()

    if model_name not in models:
        raise ValueError(
            f"Unknown model: {model_name}"
        )

    model = models[model_name]

    features = df[
        feature_names
    ].to_numpy(dtype=float)

    # Project convention:
    #
    # raw model score
    #        ↓
    # anomaly score = -raw score
    #
    # Higher anomaly score = more anomalous.

    return -np.asarray(
        model.score(features),
        dtype=float,
    ).reshape(-1)


def evaluate(
    scores,
    labels,
    threshold,
):
    scores = np.asarray(
        scores,
        dtype=float,
    )

    labels = np.asarray(
        labels,
        dtype=int,
    )

    predictions = (
        scores > threshold
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
        2.0 * precision * recall
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


def process(
    engine,
    df,
    scores,
):
    results = []

    for i, row in df.iterrows():

        result = engine.process(
            score=float(
                scores[i]
            ),
            temperature=float(
                row["temperature"]
            ),
        )

        results.append(result)

    return results


def threshold(engine):
    value = (
        engine.adaptive_threshold
        .get_threshold()
    )

    if value is None:
        raise AssertionError(
            "Engine has no active threshold."
        )

    return float(value)


def run_model(
    model_name,
    calibration_df,
    calibration_scores,
    seasonal_df,
    seasonal_scores,
    spikes_df,
    spike_scores,
):
    print()
    print("=" * 80)
    print(
        f"{model_name.upper()} — "
        "POST-ADAPTATION ANOMALY SENSITIVITY"
    )
    print("=" * 80)

    # ========================================================
    # STEP 1
    # ========================================================

    print()
    print(
        "STEP 1 — INITIAL CALIBRATION"
    )
    print("-" * 80)

    initial_engine = AdaptiveEngine()

    initial_engine.initialize(
        calibration_scores,
        model_name=model_name,
    )

    initial_threshold = threshold(
        initial_engine
    )

    print(
        f"Initial threshold : "
        f"{initial_threshold:.9f}"
    )

    # Evaluate spikes using the original threshold.
    #
    # IMPORTANT:
    # We evaluate the exact same spike scores using the
    # original calibration threshold. This gives us the
    # pre-adaptation reference.

    initial_spike_metrics = evaluate(
        spike_scores,
        spikes_df["is_anomaly"].to_numpy(),
        initial_threshold,
    )

    print_metrics(
        "TEMPERATURE SPIKES — BEFORE ADAPTATION",
        initial_spike_metrics,
    )

    # ========================================================
    # STEP 2
    # ========================================================

    print()
    print(
        "STEP 2 — SEASONAL REGIME"
    )
    print("-" * 80)

    adaptive_engine = AdaptiveEngine()

    adaptive_engine.initialize(
        calibration_scores,
        model_name=model_name,
    )

    seasonal_results = process(
        adaptive_engine,
        seasonal_df,
        seasonal_scores,
    )

    seasonal_threshold = threshold(
        adaptive_engine
    )

    confirmations = sum(
        bool(result["regime_confirmed"])
        for result in seasonal_results
    )

    alerts = sum(
        bool(result["alert"])
        for result in seasonal_results
    )

    adaptations = sum(
        bool(result["adapted"])
        for result in seasonal_results
    )

    print(
        f"Regime confirmations : "
        f"{confirmations}"
    )

    print(
        f"Alerts               : "
        f"{alerts}"
    )

    print(
        f"Adaptation updates   : "
        f"{adaptations}"
    )

    print(
        f"Initial threshold    : "
        f"{initial_threshold:.9f}"
    )

    print(
        f"Seasonal threshold   : "
        f"{seasonal_threshold:.9f}"
    )

    print(
        f"Threshold movement   : "
        f"{seasonal_threshold - initial_threshold:.9f}"
    )

    assert confirmations > 0, (
        "Seasonal regime was not confirmed."
    )

    # ========================================================
    # STEP 3
    # ========================================================

    print()
    print(
        "STEP 3 — TEMPERATURE SPIKES AFTER ADAPTATION"
    )
    print("-" * 80)

    #
    # We intentionally feed the SAME spike dataset after
    # seasonal adaptation.
    #

    post_results = process(
        adaptive_engine,
        spikes_df,
        spike_scores,
    )

    # The engine's alert field includes temporal-drift
    # alerts, so for this test we independently evaluate
    # the model score against the adapted threshold.
    #
    # This isolates the adaptive threshold's effect on
    # anomaly detection.

    post_spike_metrics = evaluate(
        spike_scores,
        spikes_df["is_anomaly"].to_numpy(),
        seasonal_threshold,
    )

    print_metrics(
        "TEMPERATURE SPIKES — AFTER ADAPTATION",
        post_spike_metrics,
    )

    # ========================================================
    # STEP 4
    # ========================================================

    print()
    print(
        "STEP 4 — BEFORE VS AFTER"
    )
    print("-" * 80)

    print(
        f"{'Metric':<15}"
        f"{'Before':>15}"
        f"{'After':>15}"
        f"{'Change':>15}"
    )

    print("-" * 60)

    print(
        f"{'TP':<15}"
        f"{initial_spike_metrics['tp']:>15}"
        f"{post_spike_metrics['tp']:>15}"
        f"{post_spike_metrics['tp'] - initial_spike_metrics['tp']:>15}"
    )

    print(
        f"{'FN':<15}"
        f"{initial_spike_metrics['fn']:>15}"
        f"{post_spike_metrics['fn']:>15}"
        f"{post_spike_metrics['fn'] - initial_spike_metrics['fn']:>15}"
    )

    print(
        f"{'FP':<15}"
        f"{initial_spike_metrics['fp']:>15}"
        f"{post_spike_metrics['fp']:>15}"
        f"{post_spike_metrics['fp'] - initial_spike_metrics['fp']:>15}"
    )

    print(
        f"{'FPR':<15}"
        f"{initial_spike_metrics['fpr']:>15.4f}"
        f"{post_spike_metrics['fpr']:>15.4f}"
        f"{post_spike_metrics['fpr'] - initial_spike_metrics['fpr']:>15.4f}"
    )

    print(
        f"{'Recall':<15}"
        f"{initial_spike_metrics['recall']:>15.4f}"
        f"{post_spike_metrics['recall']:>15.4f}"
        f"{post_spike_metrics['recall'] - initial_spike_metrics['recall']:>15.4f}"
    )

    print(
        f"{'F1':<15}"
        f"{initial_spike_metrics['f1']:>15.4f}"
        f"{post_spike_metrics['f1']:>15.4f}"
        f"{post_spike_metrics['f1'] - initial_spike_metrics['f1']:>15.4f}"
    )

    # ========================================================
    # STEP 5
    # ========================================================

    print()
    print(
        "STEP 5 — ADAPTATION SAFETY CHECK"
    )
    print("-" * 80)

    #
    # This test should NOT demand identical TP/FN before and
    # after adaptation.
    #
    # A legitimate adaptive threshold may change sensitivity.
    #
    # What we want to expose is whether the threshold becomes
    # so high that genuine anomalies disappear.
    #

    total_anomalies = int(
        np.sum(
            spikes_df["is_anomaly"]
            .to_numpy(dtype=int)
        )
    )

    print(
        f"Injected anomalies : "
        f"{total_anomalies}"
    )

    print(
        f"Detected before    : "
        f"{initial_spike_metrics['tp']}"
    )

    print(
        f"Detected after     : "
        f"{post_spike_metrics['tp']}"
    )

    print(
        f"Missed before      : "
        f"{initial_spike_metrics['fn']}"
    )

    print(
        f"Missed after       : "
        f"{post_spike_metrics['fn']}"
    )

    #
    # We don't hard-code an arbitrary model-independent recall
    # requirement here. Instead, flag a serious regression.
    #
    # Losing more than half of the previously detected
    # injected anomalies means adaptation is probably making
    # the threshold dangerously permissive.
    #

    if (
        initial_spike_metrics["tp"] > 0
        and post_spike_metrics["tp"]
        < initial_spike_metrics["tp"] * 0.5
    ):
        raise AssertionError(
            "Adaptive threshold caused a severe loss "
            "of anomaly detection sensitivity."
        )

    print()
    print(
        "[PASS] Adaptive threshold did not cause "
        "a severe loss of anomaly sensitivity."
    )

    # ========================================================
    # STEP 6
    # ========================================================

    print()
    print(
        "STEP 6 — FINAL ENGINE STATE"
    )
    print("-" * 80)

    state = adaptive_engine.get_state()

    print(
        f"State                : "
        f"{state['state']}"
    )

    print(
        f"Adaptation updates   : "
        f"{state['adaptation_updates']}"
    )

    print(
        f"Alerts               : "
        f"{state['alert_count']}"
    )

    print(
        f"Regime confirmations : "
        f"{state['regime_confirmation_count']}"
    )

    print(
        f"Final threshold      : "
        f"{threshold(adaptive_engine):.9f}"
    )


def main():

    print("=" * 80)
    print(
        "POST-ADAPTATION ANOMALY SENSITIVITY TEST"
    )
    print("=" * 80)

    print()
    print(
        "Question:"
    )

    print(
        "Does seasonal adaptation reduce false positives "
        "without making genuine anomalies disappear?"
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

    print()
    print(
        "Generating model scores..."
    )

    for model_name in MODELS:

        calibration_scores = get_scores(
            calibration_df,
            model_name,
        )

        seasonal_scores = get_scores(
            seasonal_df,
            model_name,
        )

        spike_scores = get_scores(
            spikes_df,
            model_name,
        )

        run_model(
            model_name,
            calibration_df,
            calibration_scores,
            seasonal_df,
            seasonal_scores,
            spikes_df,
            spike_scores,
        )

    print()
    print("=" * 80)
    print(
        "POST-ADAPTATION SENSITIVITY TEST COMPLETED"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()