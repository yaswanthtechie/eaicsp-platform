from pathlib import Path

import numpy as np
import pandas as pd

from src.adaptive_engine import AdaptiveEngine


# ================================================================
# PATHS
# ================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"

CALIBRATION = OUTPUT_DIR / "calibration_normal.csv"
SEASONAL = OUTPUT_DIR / "test_seasonal_normal.csv"
DRIFT = OUTPUT_DIR / "test_temperature_drift.csv"
SPIKES = OUTPUT_DIR / "test_temperature_spike.csv"


# ================================================================
# MODELS
# ================================================================

MODEL_NAMES = (
    "iforest",
    "lof",
    "ocsvm",
)


# ================================================================
# MODEL-SPECIFIC REGIME CONFIGURATION
# ================================================================
#
# From the latest regime calibration:
#
# IFOREST:
#     successful range = 1.00 -> 1.75
#     selected sigma   = 1.50
#     tolerance        = 0.20
#
# LOF:
#     successful range = 1.50 -> 3.25
#     selected sigma   = 2.50
#     tolerance        = 0.30
#
# OCSVM:
#     successful range = 1.50 -> 3.00
#     selected sigma   = 2.25
#     tolerance        = 0.20
# ================================================================

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


# ================================================================
# MODEL-SPECIFIC PERCENTILE CONFIGURATION
# ================================================================
#
# Selected from the latest adaptive-percentile sweep.
#
# IFOREST:
#     P97 -> good drift recall
#     P98 -> better seasonal FPR while retaining >30% drift recall
#     P99+ -> too aggressive
#
# LOF:
#     P97 -> best current balance
#
# OCSVM:
#     P97 -> best current balance
#
# These are validation values, not production values yet.
# ================================================================

MODEL_PERCENTILE_CONFIG = {
    "iforest": 98.0,
    "lof": 97.0,
    "ocsvm": 97.0,
}


# ================================================================
# VALIDATION REQUIREMENTS
# ================================================================

# Minimum acceptable drift recall for the selected percentile.
#
# This prevents a percentile from being selected merely because
# it dramatically reduces seasonal FPR while destroying anomaly
# sensitivity.
MIN_DRIFT_RECALL = 0.30

EPSILON = 1e-12


# ================================================================
# DATA LOADING
# ================================================================

def load_dataset(path):
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Required validation dataset not found:\n{path}"
        )

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
            f"{path} is missing required columns: "
            f"{sorted(missing)}"
        )

    return df


# ================================================================
# MODEL SCORES
# ================================================================

def get_scores(df, model_name):
    from src.model_loader import feature_names, get_models

    models = get_models()

    if model_name not in models:
        raise ValueError(
            f"Unknown model: {model_name}"
        )

    model = models[model_name]

    X = (
        df[feature_names]
        .to_numpy(dtype=float)
    )

    raw_scores = model.score(X)

    scores = -np.asarray(
        raw_scores,
        dtype=float,
    ).reshape(-1)

    if len(scores) != len(df):
        raise ValueError(
            f"{model_name} produced {len(scores)} scores "
            f"for {len(df)} rows."
        )

    if not np.all(np.isfinite(scores)):
        raise ValueError(
            f"{model_name} produced non-finite scores."
        )

    return scores


# ================================================================
# FIXED THRESHOLD
# ================================================================

def calculate_fixed_threshold(
    calibration_scores,
    percentile,
):
    return float(
        np.percentile(
            np.asarray(
                calibration_scores,
                dtype=float,
            ),
            percentile,
        )
    )


def fixed_predict(
    scores,
    threshold,
):
    return (
        np.asarray(
            scores,
            dtype=float,
        )
        > threshold
    ).astype(int)


# ================================================================
# METRICS
# ================================================================

def calculate_metrics(
    labels,
    predictions,
):
    labels = np.asarray(
        labels,
        dtype=int,
    )

    predictions = np.asarray(
        predictions,
        dtype=int,
    )

    if len(labels) != len(predictions):
        raise ValueError(
            "Labels and predictions must have equal length."
        )

    tp = int(
        np.sum(
            (labels == 1)
            & (predictions == 1)
        )
    )

    tn = int(
        np.sum(
            (labels == 0)
            & (predictions == 0)
        )
    )

    fp = int(
        np.sum(
            (labels == 0)
            & (predictions == 1)
        )
    )

    fn = int(
        np.sum(
            (labels == 1)
            & (predictions == 0)
        )
    )

    precision = (
        tp / (tp + fp)
        if tp + fp > 0
        else 0.0
    )

    recall = (
        tp / (tp + fn)
        if tp + fn > 0
        else 0.0
    )

    f1 = (
        2.0
        * precision
        * recall
        / (precision + recall)
        if precision + recall > 0
        else 0.0
    )

    accuracy = (
        (tp + tn) / len(labels)
        if len(labels) > 0
        else 0.0
    )

    fpr = (
        fp / (fp + tn)
        if fp + tn > 0
        else 0.0
    )

    fnr = (
        fn / (fn + tp)
        if fn + tp > 0
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
        "accuracy": accuracy,
        "fpr": fpr,
        "fnr": fnr,
    }


# ================================================================
# ENGINE
# ================================================================

def create_engine(
    calibration_scores,
    model_name,
    percentile,
):
    """
    Create an AdaptiveEngine with the model-specific regime
    configuration and percentile selected by the latest
    validation work.
    """

    engine = AdaptiveEngine()

    engine.initialize(
        calibration_scores,
        model_name=model_name,
    )

    # ------------------------------------------------------------
    # Model-specific regime configuration.
    # ------------------------------------------------------------

    regime_config = MODEL_REGIME_CONFIG.get(
        model_name
    )

    if regime_config is None:
        raise ValueError(
            f"No regime configuration for {model_name}."
        )

    detector = engine.regime_detector

    detector.shift_sigma = float(
        regime_config["shift_sigma"]
    )

    detector.stability_tolerance = float(
        regime_config["stability_tolerance"]
    )

    # ------------------------------------------------------------
    # Model-specific percentile.
    #
    # AdaptiveThreshold already has a calibrated initial
    # threshold from engine.initialize().
    #
    # We explicitly configure the percentile so the adaptive
    # threshold uses the same percentile as the fixed baseline.
    # ------------------------------------------------------------

    adaptive_threshold = (
        engine.adaptive_threshold
    )

    adaptive_threshold.percentile = float(
        percentile
    )

    # ------------------------------------------------------------
    # Recalculate the initial fixed calibration threshold at
    # the selected percentile.
    #
    # The adaptive threshold must start exactly here.
    # ------------------------------------------------------------

    calibration_values = np.asarray(
        calibration_scores,
        dtype=float,
    )

    initial_threshold = float(
        np.percentile(
            calibration_values,
            percentile,
        )
    )

    adaptive_threshold.initial_threshold = (
        initial_threshold
    )

    return engine


def get_threshold(engine):
    threshold = (
        engine.adaptive_threshold.get_threshold()
    )

    if threshold is None:
        raise AssertionError(
            "Adaptive threshold became None."
        )

    return float(threshold)


# ================================================================
# STREAM PROCESSING
# ================================================================

def process_stream(
    engine,
    df,
    scores,
):
    if len(df) != len(scores):
        raise ValueError(
            "Dataset and scores must have equal length."
        )

    results = []

    for index in range(len(df)):

        row = df.iloc[index]

        result = engine.process(
            score=float(
                scores[index]
            ),
            temperature=float(
                row["temperature"]
            ),
        )

        results.append(
            dict(result)
        )

    return results


# ================================================================
# RESULT HELPERS
# ================================================================

def adaptive_predictions(results):
    return np.asarray(
        [
            int(
                bool(
                    result.get(
                        "is_anomaly",
                        False,
                    )
                )
            )
            for result in results
        ],
        dtype=int,
    )


def result_thresholds(results):
    thresholds = []

    for result in results:

        threshold = result.get(
            "threshold"
        )

        if threshold is None:
            thresholds.append(
                np.nan
            )
        else:
            thresholds.append(
                float(threshold)
            )

    return np.asarray(
        thresholds,
        dtype=float,
    )


def count_flag(
    results,
    key,
):
    return sum(
        bool(
            result.get(
                key,
                False,
            )
        )
        for result in results
    )


def threshold_change_count(
    thresholds,
):
    valid = thresholds[
        np.isfinite(thresholds)
    ]

    if len(valid) < 2:
        return 0

    return int(
        np.sum(
            np.abs(
                np.diff(valid)
            )
            > EPSILON
        )
    )


# ================================================================
# PHASE SUMMARY
# ================================================================

def phase_summary(
    phase_name,
    df,
    scores,
    calibration_scores,
    fixed_threshold,
    model_name,
    percentile,
):
    labels = (
        df["is_anomaly"]
        .astype(int)
        .to_numpy()
    )

    # ------------------------------------------------------------
    # FIXED
    # ------------------------------------------------------------

    fixed_predictions = fixed_predict(
        scores,
        fixed_threshold,
    )

    fixed_metrics = calculate_metrics(
        labels,
        fixed_predictions,
    )

    # ------------------------------------------------------------
    # ADAPTIVE
    #
    # Each phase gets a fresh engine here. This phase table is
    # diagnostic only.
    #
    # The actual lifecycle validation is performed by the
    # continuous stream below.
    # ------------------------------------------------------------

    engine = create_engine(
        calibration_scores,
        model_name,
        percentile,
    )

    initial_threshold = get_threshold(
        engine
    )

    results = process_stream(
        engine,
        df,
        scores,
    )

    adaptive_predictions_array = (
        adaptive_predictions(
            results
        )
    )

    adaptive_metrics = calculate_metrics(
        labels,
        adaptive_predictions_array,
    )

    thresholds = result_thresholds(
        results
    )

    final_threshold = get_threshold(
        engine
    )

    return {
        "phase": phase_name,
        "samples": len(df),
        "anomalies": int(
            np.sum(labels)
        ),
        "fixed": fixed_metrics,
        "adaptive": adaptive_metrics,
        "initial_threshold": initial_threshold,
        "final_threshold": final_threshold,
        "threshold_changes": (
            threshold_change_count(
                thresholds
            )
        ),
        "adaptations": count_flag(
            results,
            "adapted",
        ),
        "regime_changes": count_flag(
            results,
            "regime_changed",
        ),
        "confirmations": count_flag(
            results,
            "regime_confirmed",
        ),
        "acceptances": count_flag(
            results,
            "regime_accepted",
        ),
        "drift": count_flag(
            results,
            "temporal_drift",
        ),
        "alerts": count_flag(
            results,
            "alert",
        ),
    }


# ================================================================
# PHASE TABLE
# ================================================================

def print_phase_table(
    phase_results,
):
    print()
    print(
        "PHASE PERFORMANCE"
    )
    print("-" * 112)

    print(
        f"{'Phase':<20}"
        f"{'Fixed FPR':>11}"
        f"{'Adapt FPR':>11}"
        f"{'Fixed F1':>11}"
        f"{'Adapt F1':>11}"
        f"{'Delta F1':>10}"
        f"{'Adapt':>9}"
        f"{'Accept':>9}"
    )

    print("-" * 112)

    for item in phase_results:

        fixed = item["fixed"]
        adaptive = item["adaptive"]

        delta_f1 = (
            adaptive["f1"]
            - fixed["f1"]
        )

        print(
            f"{item['phase']:<20}"
            f"{fixed['fpr']:>10.2%}"
            f"{adaptive['fpr']:>11.2%}"
            f"{fixed['f1']:>11.4f}"
            f"{adaptive['f1']:>11.4f}"
            f"{delta_f1:>+10.4f}"
            f"{item['adaptations']:>9}"
            f"{item['acceptances']:>9}"
        )


# ================================================================
# LIFECYCLE TABLE
# ================================================================

def print_lifecycle_table(
    phase_results,
):
    print()
    print(
        "PHASE LIFECYCLE"
    )
    print("-" * 112)

    print(
        f"{'Phase':<20}"
        f"{'Threshold Start':>18}"
        f"{'Threshold End':>18}"
        f"{'Changes':>9}"
        f"{'Confirm':>9}"
        f"{'Accept':>9}"
        f"{'Drift':>9}"
        f"{'Alerts':>9}"
    )

    print("-" * 112)

    for item in phase_results:

        print(
            f"{item['phase']:<20}"
            f"{item['initial_threshold']:>18.9g}"
            f"{item['final_threshold']:>18.9g}"
            f"{item['threshold_changes']:>9}"
            f"{item['confirmations']:>9}"
            f"{item['acceptances']:>9}"
            f"{item['drift']:>9}"
            f"{item['alerts']:>9}"
        )


# ================================================================
# CONTINUOUS STREAM
# ================================================================

def evaluate_continuous_stream(
    model_name,
    calibration_df,
    calibration_scores,
    seasonal_df,
    seasonal_scores,
    drift_df,
    drift_scores,
    spikes_df,
    spike_scores,
    fixed_threshold,
    percentile,
):
    """
    Run ONE AdaptiveEngine through:

        NORMAL
          |
          v
        SEASONAL NORMAL
          |
          v
        TEMPORAL DRIFT
          |
          v
        TEMPERATURE SPIKES

    This is the primary lifecycle test.
    """

    engine = create_engine(
        calibration_scores,
        model_name,
        percentile,
    )

    initial_threshold = get_threshold(
        engine
    )

    all_results = []

    # ------------------------------------------------------------
    # NORMAL
    # ------------------------------------------------------------

    normal_start = len(
        all_results
    )

    all_results.extend(
        process_stream(
            engine,
            calibration_df,
            calibration_scores,
        )
    )

    normal_end = len(
        all_results
    )

    normal_threshold = get_threshold(
        engine
    )

    # ------------------------------------------------------------
    # SEASONAL
    # ------------------------------------------------------------

    seasonal_start = len(
        all_results
    )

    all_results.extend(
        process_stream(
            engine,
            seasonal_df,
            seasonal_scores,
        )
    )

    seasonal_end = len(
        all_results
    )

    seasonal_threshold = (
        get_threshold(engine)
    )

    # ------------------------------------------------------------
    # DRIFT
    # ------------------------------------------------------------

    drift_start = len(
        all_results
    )

    all_results.extend(
        process_stream(
            engine,
            drift_df,
            drift_scores,
        )
    )

    drift_end = len(
        all_results
    )

    drift_threshold = (
        get_threshold(engine)
    )

    # ------------------------------------------------------------
    # SPIKES
    # ------------------------------------------------------------

    spike_start = len(
        all_results
    )

    all_results.extend(
        process_stream(
            engine,
            spikes_df,
            spike_scores,
        )
    )

    spike_end = len(
        all_results
    )

    final_threshold = (
        get_threshold(engine)
    )

    # ------------------------------------------------------------
    # Combined data
    # ------------------------------------------------------------

    combined_df = pd.concat(
        [
            calibration_df,
            seasonal_df,
            drift_df,
            spikes_df,
        ],
        ignore_index=True,
    )

    combined_scores = np.concatenate(
        [
            calibration_scores,
            seasonal_scores,
            drift_scores,
            spike_scores,
        ]
    )

    labels = (
        combined_df["is_anomaly"]
        .astype(int)
        .to_numpy()
    )

    # ------------------------------------------------------------
    # Fixed
    # ------------------------------------------------------------

    fixed_predictions = fixed_predict(
        combined_scores,
        fixed_threshold,
    )

    fixed_metrics = calculate_metrics(
        labels,
        fixed_predictions,
    )

    # ------------------------------------------------------------
    # Adaptive
    # ------------------------------------------------------------

    adaptive_predictions_array = (
        adaptive_predictions(
            all_results
        )
    )

    adaptive_metrics = calculate_metrics(
        labels,
        adaptive_predictions_array,
    )

    thresholds = result_thresholds(
        all_results
    )

    return {
        "fixed": fixed_metrics,
        "adaptive": adaptive_metrics,
        "initial_threshold": initial_threshold,
        "normal_threshold": normal_threshold,
        "seasonal_threshold": seasonal_threshold,
        "drift_threshold": drift_threshold,
        "final_threshold": final_threshold,
        "threshold_changes": (
            threshold_change_count(
                thresholds
            )
        ),
        "adaptations": count_flag(
            all_results,
            "adapted",
        ),
        "regime_changes": count_flag(
            all_results,
            "regime_changed",
        ),
        "confirmations": count_flag(
            all_results,
            "regime_confirmed",
        ),
        "acceptances": count_flag(
            all_results,
            "regime_accepted",
        ),
        "drift": count_flag(
            all_results,
            "temporal_drift",
        ),
        "alerts": count_flag(
            all_results,
            "alert",
        ),
        "results": all_results,
        "thresholds": thresholds,
        "normal_start": normal_start,
        "normal_end": normal_end,
        "seasonal_start": seasonal_start,
        "seasonal_end": seasonal_end,
        "drift_start": drift_start,
        "drift_end": drift_end,
        "spike_start": spike_start,
        "spike_end": spike_end,
    }


# ================================================================
# RANGE METRICS
# ================================================================

def metrics_for_range(
    labels,
    predictions,
    start,
    end,
):
    return calculate_metrics(
        labels[start:end],
        predictions[start:end],
    )


# ================================================================
# DRIFT FREEZE
# ================================================================

def verify_drift_freeze(
    continuous,
):
    """
    Once temporal drift is detected, the threshold must remain
    unchanged through the rest of the stream.
    """

    thresholds = continuous[
        "thresholds"
    ]

    all_results = continuous[
        "results"
    ]

    drift_indices = [
        index
        for index, result in enumerate(
            all_results
        )
        if result.get(
            "temporal_drift",
            False,
        )
    ]

    if not drift_indices:
        return False

    first_drift = drift_indices[0]

    if first_drift >= len(
        thresholds
    ):
        return False

    frozen_threshold = (
        thresholds[first_drift]
    )

    if not np.isfinite(
        frozen_threshold
    ):
        return False

    after_drift = thresholds[
        first_drift:
    ]

    valid = after_drift[
        np.isfinite(after_drift)
    ]

    if len(valid) == 0:
        return False

    return bool(
        np.allclose(
            valid,
            frozen_threshold,
            rtol=1e-12,
            atol=1e-12,
        )
    )


# ================================================================
# SPIKE FREEZE
# ================================================================

def verify_spike_freeze(
    continuous,
):
    """
    Temperature spikes must not cause the adaptive threshold
    to move after the threshold has already been established.
    """

    thresholds = continuous[
        "thresholds"
    ]

    spike_start = continuous[
        "spike_start"
    ]

    spike_end = continuous[
        "spike_end"
    ]

    if spike_end <= spike_start:
        return False

    spike_thresholds = thresholds[
        spike_start:spike_end
    ]

    valid = spike_thresholds[
        np.isfinite(spike_thresholds)
    ]

    if len(valid) == 0:
        return False

    expected = continuous[
        "drift_threshold"
    ]

    return bool(
        np.allclose(
            valid,
            expected,
            rtol=1e-12,
            atol=1e-12,
        )
    )


# ================================================================
# MODEL LIFECYCLE VALIDATION
# ================================================================

def validate_model_lifecycle(
    model_name,
    continuous,
    combined_labels,
    combined_predictions,
):
    """
    Validate lifecycle correctness.

    We intentionally do NOT require adaptive F1 to beat fixed F1.
    The purpose of this test is to establish that adaptation is
    selective, stable, and safe.
    """

    initial_threshold = continuous[
        "initial_threshold"
    ]

    normal_threshold = continuous[
        "normal_threshold"
    ]

    seasonal_threshold = continuous[
        "seasonal_threshold"
    ]

    drift_threshold = continuous[
        "drift_threshold"
    ]

    final_threshold = continuous[
        "final_threshold"
    ]

    acceptances = continuous[
        "acceptances"
    ]

    drift_count = continuous[
        "drift"
    ]

    # ------------------------------------------------------------
    # 1. Initial threshold exists.
    # ------------------------------------------------------------

    if not np.isfinite(
        initial_threshold
    ):
        raise AssertionError(
            f"{model_name}: initial threshold "
            f"is not finite."
        )

    # ------------------------------------------------------------
    # 2. Normal phase must not adapt.
    # ------------------------------------------------------------

    if not np.isclose(
        normal_threshold,
        initial_threshold,
        rtol=1e-12,
        atol=1e-12,
    ):
        raise AssertionError(
            f"{model_name}: threshold changed "
            f"during normal calibration phase."
        )

    # ------------------------------------------------------------
    # 3. Seasonal regime must be accepted.
    # ------------------------------------------------------------

    if acceptances < 1:
        raise AssertionError(
            f"{model_name}: seasonal regime "
            f"was not accepted."
        )

    # ------------------------------------------------------------
    # 4. Seasonal acceptance must actually change threshold.
    # ------------------------------------------------------------

    if np.isclose(
        seasonal_threshold,
        initial_threshold,
        rtol=1e-12,
        atol=1e-12,
    ):
        raise AssertionError(
            f"{model_name}: seasonal regime was accepted "
            f"but threshold did not change."
        )

    # ------------------------------------------------------------
    # 5. Drift must be detected.
    # ------------------------------------------------------------

    if drift_count < 1:
        raise AssertionError(
            f"{model_name}: temporal drift "
            f"was not detected."
        )

    # ------------------------------------------------------------
    # 6. Threshold frozen during drift.
    # ------------------------------------------------------------

    if not np.isclose(
        drift_threshold,
        seasonal_threshold,
        rtol=1e-12,
        atol=1e-12,
    ):
        raise AssertionError(
            f"{model_name}: threshold changed "
            f"after temporal drift."
        )

    # ------------------------------------------------------------
    # 7. Threshold frozen through spikes.
    # ------------------------------------------------------------

    if not verify_spike_freeze(
        continuous
    ):
        raise AssertionError(
            f"{model_name}: threshold changed "
            f"during temperature spikes."
        )

    # ------------------------------------------------------------
    # 8. Final threshold remains the seasonal threshold.
    # ------------------------------------------------------------

    if not np.isclose(
        final_threshold,
        seasonal_threshold,
        rtol=1e-12,
        atol=1e-12,
    ):
        raise AssertionError(
            f"{model_name}: final threshold differs "
            f"from the accepted seasonal threshold."
        )

    # ------------------------------------------------------------
    # 9. Drift freeze verification.
    # ------------------------------------------------------------

    if not verify_drift_freeze(
        continuous
    ):
        raise AssertionError(
            f"{model_name}: threshold was not frozen "
            f"after temporal drift detection."
        )

    # ------------------------------------------------------------
    # 10. Selected percentile must preserve enough drift recall.
    #
    # This protects against the earlier IForest P99.5 problem.
    # ------------------------------------------------------------

    drift_start = continuous[
        "drift_start"
    ]

    drift_end = continuous[
        "drift_end"
    ]

    adaptive_drift_metrics = (
        metrics_for_range(
            combined_labels,
            combined_predictions,
            drift_start,
            drift_end,
        )
    )

    if (
        adaptive_drift_metrics["recall"]
        < MIN_DRIFT_RECALL
    ):
        raise AssertionError(
            f"{model_name}: selected percentile produced "
            f"drift recall "
            f"{adaptive_drift_metrics['recall']:.2%}, "
            f"below required "
            f"{MIN_DRIFT_RECALL:.2%}."
        )

    return adaptive_drift_metrics


# ================================================================
# MODEL TEST
# ================================================================

def run_model(
    model_name,
    calibration_df,
    calibration_scores,
    seasonal_df,
    seasonal_scores,
    drift_df,
    drift_scores,
    spikes_df,
    spike_scores,
):
    print()
    print("#" * 88)
    print(
        f"MODEL: {model_name.upper()}"
    )
    print("#" * 88)

    percentile = float(
        MODEL_PERCENTILE_CONFIG[
            model_name
        ]
    )

    regime_config = (
        MODEL_REGIME_CONFIG[
            model_name
        ]
    )

    fixed_threshold = (
        calculate_fixed_threshold(
            calibration_scores,
            percentile,
        )
    )

    print()
    print(
        f"Fixed P{percentile:.1f} threshold : "
        f"{fixed_threshold:.12g}"
    )

    print(
        f"Adaptive percentile          : "
        f"P{percentile:.1f}"
    )

    print(
        f"Adaptive shift sigma         : "
        f"{regime_config['shift_sigma']:.2f}"
    )

    print(
        f"Stability tolerance          : "
        f"{regime_config['stability_tolerance']:.2f}"
    )

    # ------------------------------------------------------------
    # Individual phase diagnostics
    # ------------------------------------------------------------

    phase_results = []

    phase_results.append(
        phase_summary(
            "NORMAL",
            calibration_df,
            calibration_scores,
            calibration_scores,
            fixed_threshold,
            model_name,
            percentile,
        )
    )

    phase_results.append(
        phase_summary(
            "SEASONAL",
            seasonal_df,
            seasonal_scores,
            calibration_scores,
            fixed_threshold,
            model_name,
            percentile,
        )
    )

    phase_results.append(
        phase_summary(
            "DRIFT",
            drift_df,
            drift_scores,
            calibration_scores,
            fixed_threshold,
            model_name,
            percentile,
        )
    )

    phase_results.append(
        phase_summary(
            "SPIKES",
            spikes_df,
            spike_scores,
            calibration_scores,
            fixed_threshold,
            model_name,
            percentile,
        )
    )

    print_phase_table(
        phase_results
    )

    print_lifecycle_table(
        phase_results
    )

    # ------------------------------------------------------------
    # Continuous lifecycle
    # ------------------------------------------------------------

    continuous = (
        evaluate_continuous_stream(
            model_name=model_name,
            calibration_df=calibration_df,
            calibration_scores=calibration_scores,
            seasonal_df=seasonal_df,
            seasonal_scores=seasonal_scores,
            drift_df=drift_df,
            drift_scores=drift_scores,
            spikes_df=spikes_df,
            spike_scores=spike_scores,
            fixed_threshold=fixed_threshold,
            percentile=percentile,
        )
    )

    fixed = continuous[
        "fixed"
    ]

    adaptive = continuous[
        "adaptive"
    ]

    all_results = continuous[
        "results"
    ]

    combined_predictions = (
        adaptive_predictions(
            all_results
        )
    )

    combined_df = pd.concat(
        [
            calibration_df,
            seasonal_df,
            drift_df,
            spikes_df,
        ],
        ignore_index=True,
    )

    combined_labels = (
        combined_df["is_anomaly"]
        .astype(int)
        .to_numpy()
    )

    print()
    print(
        "CONTINUOUS STREAM"
    )
    print("-" * 88)

    print(
        f"Fixed F1       : "
        f"{fixed['f1']:.4f}"
    )

    print(
        f"Adaptive F1    : "
        f"{adaptive['f1']:.4f}"
    )

    print(
        f"Delta F1       : "
        f"{adaptive['f1'] - fixed['f1']:+.4f}"
    )

    print(
        f"Fixed FPR      : "
        f"{fixed['fpr']:.2%}"
    )

    print(
        f"Adaptive FPR   : "
        f"{adaptive['fpr']:.2%}"
    )

    print(
        f"Delta FPR      : "
        f"{adaptive['fpr'] - fixed['fpr']:+.2%}"
    )

    print(
        f"Fixed Recall   : "
        f"{fixed['recall']:.2%}"
    )

    print(
        f"Adaptive Recall: "
        f"{adaptive['recall']:.2%}"
    )

    print(
        f"Delta Recall   : "
        f"{adaptive['recall'] - fixed['recall']:+.2%}"
    )

    # ------------------------------------------------------------
    # Phase-specific adaptive metrics.
    # ------------------------------------------------------------

    drift_start = continuous[
        "drift_start"
    ]

    drift_end = continuous[
        "drift_end"
    ]

    spike_start = continuous[
        "spike_start"
    ]

    spike_end = continuous[
        "spike_end"
    ]

    seasonal_start = continuous[
        "seasonal_start"
    ]

    seasonal_end = continuous[
        "seasonal_end"
    ]

    adaptive_seasonal = metrics_for_range(
        combined_labels,
        combined_predictions,
        seasonal_start,
        seasonal_end,
    )

    adaptive_drift = metrics_for_range(
        combined_labels,
        combined_predictions,
        drift_start,
        drift_end,
    )

    adaptive_spikes = metrics_for_range(
        combined_labels,
        combined_predictions,
        spike_start,
        spike_end,
    )

    print()
    print(
        "ADAPTIVE PHASE METRICS"
    )
    print("-" * 88)

    print(
        f"Seasonal FPR  : "
        f"{adaptive_seasonal['fpr']:.2%}"
    )

    print(
        f"Drift Recall  : "
        f"{adaptive_drift['recall']:.2%}"
    )

    print(
        f"Drift F1      : "
        f"{adaptive_drift['f1']:.4f}"
    )

    print(
        f"Spike FPR     : "
        f"{adaptive_spikes['fpr']:.2%}"
    )

    # ------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------

    print()
    print(
        "LIFECYCLE"
    )
    print("-" * 88)

    print(
        f"Initial threshold : "
        f"{continuous['initial_threshold']:.12g}"
    )

    print(
        f"Normal threshold  : "
        f"{continuous['normal_threshold']:.12g}"
    )

    print(
        f"Seasonal threshold: "
        f"{continuous['seasonal_threshold']:.12g}"
    )

    print(
        f"Drift threshold   : "
        f"{continuous['drift_threshold']:.12g}"
    )

    print(
        f"Final threshold   : "
        f"{continuous['final_threshold']:.12g}"
    )

    print(
        f"Threshold changes : "
        f"{continuous['threshold_changes']}"
    )

    print(
        f"Adaptations       : "
        f"{continuous['adaptations']}"
    )

    print(
        f"Regime changes    : "
        f"{continuous['regime_changes']}"
    )

    print(
        f"Confirmations     : "
        f"{continuous['confirmations']}"
    )

    print(
        f"Acceptances       : "
        f"{continuous['acceptances']}"
    )

    print(
        f"Drift signals     : "
        f"{continuous['drift']}"
    )

    print(
        f"Alerts            : "
        f"{continuous['alerts']}"
    )

    # ------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------

    assert np.isclose(
        continuous["initial_threshold"],
        fixed_threshold,
        rtol=1e-12,
        atol=1e-12,
    ), (
        f"{model_name}: adaptive engine did not start "
        f"from selected fixed threshold."
    )

    print(
        "[PASS] Starts from selected fixed calibration threshold."
    )

    adaptive_drift_metrics = (
        validate_model_lifecycle(
            model_name=model_name,
            continuous=continuous,
            combined_labels=combined_labels,
            combined_predictions=combined_predictions,
        )
    )

    print(
        "[PASS] Seasonal regime accepted and threshold adapted."
    )

    print(
        "[PASS] Temporal drift detected and threshold frozen."
    )

    print(
        "[PASS] Temperature-spike phase did not change threshold."
    )

    print(
        f"[PASS] Drift recall "
        f"{adaptive_drift_metrics['recall']:.2%} "
        f">= {MIN_DRIFT_RECALL:.2%}."
    )

    return {
        "model": model_name,
        "percentile": percentile,
        "config": regime_config,
        "fixed_threshold": fixed_threshold,
        "phase_results": phase_results,
        "continuous": continuous,
        "adaptive_seasonal": adaptive_seasonal,
        "adaptive_drift": adaptive_drift,
        "adaptive_spikes": adaptive_spikes,
    }


# ================================================================
# FINAL COMPARISON
# ================================================================

def print_final_comparison(
    all_models,
):
    print()
    print("=" * 88)
    print(
        "FINAL FIXED VS ADAPTIVE COMPARISON"
    )
    print("=" * 88)

    print()
    print(
        f"{'MODEL':<10}"
        f"{'PCTL':>7}"
        f"{'SIGMA':>8}"
        f"{'FIXED F1':>12}"
        f"{'ADAPT F1':>12}"
        f"{'Delta F1':>10}"
        f"{'FIXED FPR':>12}"
        f"{'ADAPT FPR':>12}"
        f"{'Delta FPR':>10}"
    )

    print("-" * 104)

    for item in all_models:

        fixed = item[
            "continuous"
        ]["fixed"]

        adaptive = item[
            "continuous"
        ]["adaptive"]

        config = item[
            "config"
        ]

        delta_f1 = (
            adaptive["f1"]
            - fixed["f1"]
        )

        delta_fpr = (
            adaptive["fpr"]
            - fixed["fpr"]
        )

        print(
            f"{item['model']:<10}"
            f"{item['percentile']:>7.1f}"
            f"{config['shift_sigma']:>8.2f}"
            f"{fixed['f1']:>12.4f}"
            f"{adaptive['f1']:>12.4f}"
            f"{delta_f1:>+10.4f}"
            f"{fixed['fpr']:>11.2%}"
            f"{adaptive['fpr']:>12.2%}"
            f"{delta_fpr:>+10.2%}"
        )

    # ------------------------------------------------------------
    # Phase-specific summary
    # ------------------------------------------------------------

    print()
    print(
        "MODEL-SPECIFIC ADAPTIVE RESULTS"
    )
    print("-" * 88)

    print(
        f"{'MODEL':<10}"
        f"{'PCTL':>7}"
        f"{'Season FPR':>12}"
        f"{'Drift Rec':>12}"
        f"{'Drift F1':>12}"
        f"{'Spike FPR':>12}"
    )

    print("-" * 88)

    for item in all_models:

        print(
            f"{item['model']:<10}"
            f"{item['percentile']:>7.1f}"
            f"{item['adaptive_seasonal']['fpr']:>11.2%}"
            f"{item['adaptive_drift']['recall']:>12.2%}"
            f"{item['adaptive_drift']['f1']:>12.4f}"
            f"{item['adaptive_spikes']['fpr']:>12.2%}"
        )

    # ------------------------------------------------------------
    # Interpretation
    # ------------------------------------------------------------

    print()
    print(
        "FINAL INTERPRETATION"
    )
    print("-" * 88)

    for item in all_models:

        model = item[
            "model"
        ]

        continuous = item[
            "continuous"
        ]

        fixed = continuous[
            "fixed"
        ]

        adaptive = continuous[
            "adaptive"
        ]

        delta_f1 = (
            adaptive["f1"]
            - fixed["f1"]
        )

        delta_fpr = (
            adaptive["fpr"]
            - fixed["fpr"]
        )

        seasonal = item[
            "adaptive_seasonal"
        ]

        drift = item[
            "adaptive_drift"
        ]

        spikes = item[
            "adaptive_spikes"
        ]

        print()
        print(
            f"{model.upper()} "
            f"P{item['percentile']:.1f} "
            f"(sigma={item['config']['shift_sigma']:.2f})"
        )

        if (
            delta_f1 > 0
            and delta_fpr < 0
        ):
            print(
                "  [PASS] Adaptive improves F1 "
                "while reducing overall FPR."
            )

        elif delta_fpr < 0:
            print(
                "  [INFO] Adaptive reduces overall FPR "
                "but does not improve overall F1."
            )

        elif delta_f1 > 0:
            print(
                "  [INFO] Adaptive improves overall F1 "
                "but does not reduce overall FPR."
            )

        else:
            print(
                "  [INFO] No overall metric improvement; "
                "lifecycle safety remains the primary criterion."
            )

        print(
            f"  Seasonal FPR : "
            f"{seasonal['fpr']:.2%}"
        )

        print(
            f"  Drift recall : "
            f"{drift['recall']:.2%}"
        )

        print(
            f"  Drift F1     : "
            f"{drift['f1']:.4f}"
        )

        print(
            f"  Spike FPR    : "
            f"{spikes['fpr']:.2%}"
        )

        print(
            f"  Acceptances  : "
            f"{continuous['acceptances']}"
        )

        print(
            f"  Drift signals: "
            f"{continuous['drift']}"
        )


# ================================================================
# MAIN
# ================================================================

def main():

    print("=" * 88)
    print(
        "FIXED VS ADAPTIVE THRESHOLD "
        "PERFORMANCE EVALUATION"
    )
    print("=" * 88)

    print()
    print(
        "Purpose:"
    )

    print(
        "  Fixed model-specific percentile "
        "vs adaptive model-specific percentile"
    )

    print(
        "  Model-specific regime detection"
    )

    print(
        "  Seasonal adaptation"
    )

    print(
        "  Temporal-drift freeze"
    )

    print(
        "  Temperature-spike protection"
    )

    print(
        "  Drift-recall guardrail"
    )

    print()
    print(
        "MODEL CONFIGURATION"
    )

    print("-" * 88)

    for model_name in MODEL_NAMES:

        regime = MODEL_REGIME_CONFIG[
            model_name
        ]

        percentile = (
            MODEL_PERCENTILE_CONFIG[
                model_name
            ]
        )

        print(
            f"{model_name:<10} "
            f"P{percentile:.1f} "
            f"sigma={regime['shift_sigma']:.2f} "
            f"tolerance={regime['stability_tolerance']:.2f}"
        )

    print()
    print(
        f"Minimum required drift recall: "
        f"{MIN_DRIFT_RECALL:.0%}"
    )

    # ------------------------------------------------------------
    # Load datasets.
    #
    # Real validation files are mandatory.
    # ------------------------------------------------------------

    calibration_df = load_dataset(
        CALIBRATION
    )

    seasonal_df = load_dataset(
        SEASONAL
    )

    drift_df = load_dataset(
        DRIFT
    )

    spikes_df = load_dataset(
        SPIKES
    )

    print()
    print(
        "DATASETS"
    )

    print("-" * 88)

    print(
        f"Calibration : {len(calibration_df)}"
    )

    print(
        f"Seasonal    : {len(seasonal_df)}"
    )

    print(
        f"Drift       : {len(drift_df)}"
    )

    print(
        f"Spikes      : {len(spikes_df)}"
    )

    # ------------------------------------------------------------
    # Verify anomaly labels exist in validation phases.
    # ------------------------------------------------------------

    if int(
        seasonal_df["is_anomaly"].sum()
    ) != 0:
        print(
            "[INFO] Seasonal dataset contains anomaly labels."
        )

    if int(
        drift_df["is_anomaly"].sum()
    ) == 0:
        print(
            "[WARNING] Drift dataset contains no "
            "positive anomaly labels."
        )

    if int(
        spikes_df["is_anomaly"].sum()
    ) == 0:
        print(
            "[WARNING] Spike dataset contains no "
            "positive anomaly labels."
        )

    # ------------------------------------------------------------
    # Generate model scores.
    # ------------------------------------------------------------

    print()
    print(
        "GENERATING MODEL SCORES"
    )

    print("-" * 88)

    all_models = []

    for model_name in MODEL_NAMES:

        print(
            f"  {model_name.upper()}..."
        )

        calibration_scores = get_scores(
            calibration_df,
            model_name,
        )

        seasonal_scores = get_scores(
            seasonal_df,
            model_name,
        )

        drift_scores = get_scores(
            drift_df,
            model_name,
        )

        spike_scores = get_scores(
            spikes_df,
            model_name,
        )

        result = run_model(
            model_name=model_name,
            calibration_df=calibration_df,
            calibration_scores=calibration_scores,
            seasonal_df=seasonal_df,
            seasonal_scores=seasonal_scores,
            drift_df=drift_df,
            drift_scores=drift_scores,
            spikes_df=spikes_df,
            spike_scores=spike_scores,
        )

        all_models.append(
            result
        )

    print_final_comparison(
        all_models
    )

    print()
    print("=" * 88)
    print(
        "FIXED VS ADAPTIVE PERFORMANCE "
        "EVALUATION COMPLETED"
    )
    print("=" * 88)


if __name__ == "__main__":
    main()