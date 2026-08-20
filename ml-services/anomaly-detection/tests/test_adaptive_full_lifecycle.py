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


MODELS = (
    "iforest",
    "lof",
    "ocsvm",
)


# ============================================================
# FINAL MODEL-SPECIFIC CONFIGURATION
# ============================================================

MODEL_CONFIG = {
    "iforest": {
        "percentile": 98.0,
        "shift_sigma": 1.50,
        "stability_tolerance": 0.20,
    },
    "lof": {
        "percentile": 97.0,
        "shift_sigma": 2.50,
        "stability_tolerance": 0.30,
    },
    "ocsvm": {
        "percentile": 97.0,
        "shift_sigma": 2.25,
        "stability_tolerance": 0.20,
    },
}


BASELINE_SIZE = 100
CANDIDATE_SIZES = [10, 25, 50, 100, 200]
MIN_STABLE_BLOCKS = 2
ADAPTIVE_WINDOW_SIZE = 50


# ============================================================
# DATA
# ============================================================

def load_dataset(path):
    df = pd.read_csv(path)

    required = {
        "timestamp",
        "temperature",
        "humidity",
        "stock_count",
        "is_anomaly",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"{path} is missing columns: {sorted(missing)}"
        )

    return df.reset_index(drop=True)


# ============================================================
# MODEL SCORES
# ============================================================

def get_scores(df, model_name):
    from src.model_loader import get_models, feature_names

    models = get_models()

    if model_name not in models:
        raise ValueError(
            f"Unknown model: {model_name}"
        )

    features = df[
        feature_names
    ].to_numpy(dtype=float)

    model = models[model_name]

    # Project convention:
    #
    # raw model score -> anomaly score = -raw score
    #
    # Higher anomaly score = more anomalous.

    scores = -np.asarray(
        model.score(features),
        dtype=float,
    ).reshape(-1)

    if len(scores) != len(df):
        raise AssertionError(
            f"{model_name}: score length "
            f"{len(scores)} != dataset length "
            f"{len(df)}"
        )

    return scores


# ============================================================
# ENGINE
# ============================================================

def create_engine(model_name):
    config = MODEL_CONFIG[model_name]

    return AdaptiveEngine(
        baseline_size=BASELINE_SIZE,
        candidate_sizes=CANDIDATE_SIZES,
        shift_sigma=config["shift_sigma"],
        stability_tolerance=config[
            "stability_tolerance"
        ],
        min_stable_blocks=MIN_STABLE_BLOCKS,
        adaptive_window_size=ADAPTIVE_WINDOW_SIZE,
        adaptive_percentile=config[
            "percentile"
        ],
    )


# ============================================================
# STREAM PROCESSING
# ============================================================

def process_dataset(
    engine,
    df,
    scores,
):
    results = []

    for index in range(len(df)):

        result = engine.process(
            score=float(scores[index]),
            temperature=float(
                df.iloc[index]["temperature"]
            ),
        )

        results.append(result)

    return results


def count(results, key):
    return sum(
        bool(
            result.get(
                key,
                False,
            )
        )
        for result in results
    )


# ============================================================
# THRESHOLD
# ============================================================

def get_threshold(engine):
    threshold = (
        engine.adaptive_threshold.get_threshold()
    )

    if threshold is None:
        raise AssertionError(
            "Adaptive engine has no active threshold."
        )

    return float(threshold)


# ============================================================
# CONFUSION MATRIX
# ============================================================

def confusion_matrix(
    df,
    scores,
    threshold,
):
    labels = df[
        "is_anomaly"
    ].to_numpy(dtype=int)

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

    return tp, tn, fp, fn


def print_matrix(
    title,
    matrix,
):
    tp, tn, fp, fn = matrix

    print()
    print(title)
    print("-" * 55)
    print(
        f"TP={tp:<7} "
        f"TN={tn:<7} "
        f"FP={fp:<7} "
        f"FN={fn:<7}"
    )


# ============================================================
# PHASE SUMMARY
# ============================================================

def phase_summary(
    name,
    results,
):
    print(
        f"{name:<24} "
        f"confirmed={count(results, 'regime_confirmed'):<5} "
        f"changed={count(results, 'regime_changed'):<5} "
        f"adapted={count(results, 'adapted'):<5} "
        f"alerts={count(results, 'alert'):<5} "
        f"drift={count(results, 'temporal_drift'):<5}"
    )


# ============================================================
# MODEL TEST
# ============================================================

def run_model(
    model_name,
    calibration_df,
    calibration_scores,
    seasonal_df,
    seasonal_scores,
    spikes_df,
    spike_scores,
    drift_df,
    drift_scores,
):
    config = MODEL_CONFIG[
        model_name
    ]

    print()
    print("#" * 88)
    print(
        f"MODEL: {model_name.upper()}"
    )
    print("#" * 88)

    print(
        f"Configuration: "
        f"P{config['percentile']:.1f} | "
        f"sigma={config['shift_sigma']:.2f} | "
        f"tolerance={config['stability_tolerance']:.2f}"
    )

    engine = create_engine(
        model_name
    )

    # ========================================================
    # PHASE 1
    # ========================================================

    print()
    print(
        "PHASE 1 — ORIGINAL CALIBRATION"
    )
    print("-" * 88)

    engine.initialize(
        calibration_scores
    )

    initial_threshold = get_threshold(
        engine
    )

    print(
        f"Initial threshold : "
        f"{initial_threshold:.12f}"
    )

    calibration_matrix = confusion_matrix(
        calibration_df,
        calibration_scores,
        initial_threshold,
    )

    print_matrix(
        "Calibration confusion matrix",
        calibration_matrix,
    )

    # ========================================================
    # PHASE 2 — SEASONAL
    # ========================================================

    print()
    print(
        "PHASE 2 — SEASONAL REGIME TRANSITION"
    )
    print("-" * 88)

    seasonal_results = process_dataset(
        engine,
        seasonal_df,
        seasonal_scores,
    )

    seasonal_threshold = get_threshold(
        engine
    )

    seasonal_confirmed = count(
        seasonal_results,
        "regime_confirmed",
    )

    seasonal_changed = count(
        seasonal_results,
        "regime_changed",
    )

    seasonal_alerts = count(
        seasonal_results,
        "alert",
    )

    seasonal_adaptations = count(
        seasonal_results,
        "adapted",
    )

    phase_summary(
        "Seasonal",
        seasonal_results,
    )

    print(
        f"Threshold : "
        f"{initial_threshold:.12f}"
        f" -> "
        f"{seasonal_threshold:.12f}"
    )

    print(
        f"Movement  : "
        f"{seasonal_threshold - initial_threshold:.12f}"
    )

    assert seasonal_confirmed > 0, (
        f"{model_name}: seasonal regime "
        f"was never confirmed."
    )

    assert seasonal_changed > 0, (
        f"{model_name}: seasonal regime "
        f"was never marked as changed."
    )

    assert seasonal_alerts == 0, (
        f"{model_name}: seasonal normal data "
        f"produced temporal alerts."
    )

    assert seasonal_adaptations > 0, (
        f"{model_name}: seasonal regime "
        f"was confirmed but no adaptation occurred."
    )

    assert (
        not np.isclose(
            seasonal_threshold,
            initial_threshold,
            rtol=0.0,
            atol=1e-15,
        )
    ), (
        f"{model_name}: seasonal adaptation "
        f"did not change threshold."
    )

    print(
        "[PASS] Seasonal regime confirmed, "
        "accepted and adapted."
    )

    # ========================================================
    # PHASE 3 — CONTINUED SEASONAL
    # ========================================================

    print()
    print(
        "PHASE 3 — CONTINUED SEASONAL OPERATION"
    )
    print("-" * 88)

    threshold_before_continued = (
        get_threshold(engine)
    )

    continued_results = process_dataset(
        engine,
        seasonal_df,
        seasonal_scores,
    )

    threshold_after_continued = (
        get_threshold(engine)
    )

    continued_alerts = count(
        continued_results,
        "alert",
    )

    continued_adaptations = count(
        continued_results,
        "adapted",
    )

    phase_summary(
        "Continued seasonal",
        continued_results,
    )

    print(
        f"Threshold : "
        f"{threshold_before_continued:.12f}"
        f" -> "
        f"{threshold_after_continued:.12f}"
    )

    assert continued_alerts == 0, (
        f"{model_name}: continued seasonal "
        f"operation generated alerts."
    )

    assert continued_adaptations == 0, (
        f"{model_name}: continued seasonal "
        f"operation repeatedly adapted threshold."
    )

    assert np.isclose(
        threshold_after_continued,
        threshold_before_continued,
        rtol=0.0,
        atol=1e-15,
    ), (
        f"{model_name}: threshold changed "
        f"during stable continued operation."
    )

    print(
        "[PASS] Continued seasonal operation "
        "remained stable."
    )

    # ========================================================
    # PHASE 4 — TEMPERATURE SPIKES
    # ========================================================

    print()
    print(
        "PHASE 4 — TEMPERATURE SPIKES"
    )
    print("-" * 88)

    spike_threshold_before = (
        get_threshold(engine)
    )

    spike_results = process_dataset(
        engine,
        spikes_df,
        spike_scores,
    )

    spike_threshold_after = (
        get_threshold(engine)
    )

    spike_temporal = count(
        spike_results,
        "temporal_drift",
    )

    spike_alerts = count(
        spike_results,
        "alert",
    )

    spike_adaptations = count(
        spike_results,
        "adapted",
    )

    phase_summary(
        "Temperature spikes",
        spike_results,
    )

    spike_matrix = confusion_matrix(
        spikes_df,
        spike_scores,
        spike_threshold_before,
    )

    print_matrix(
        "Spikes using seasonal threshold",
        spike_matrix,
    )

    print(
        f"Threshold : "
        f"{spike_threshold_before:.12f}"
        f" -> "
        f"{spike_threshold_after:.12f}"
    )

    print(
        f"Temporal drift signals : "
        f"{spike_temporal}"
    )

    print(
        f"Alerts                 : "
        f"{spike_alerts}"
    )

    print(
        f"Adaptations            : "
        f"{spike_adaptations}"
    )

    assert spike_temporal == 0, (
        f"{model_name}: temperature spikes "
        f"were classified as sustained temporal drift."
    )

    assert spike_adaptations == 0, (
        f"{model_name}: temperature spikes "
        f"caused adaptive threshold updates."
    )

    assert np.isclose(
        spike_threshold_after,
        spike_threshold_before,
        rtol=0.0,
        atol=1e-15,
    ), (
        f"{model_name}: threshold changed "
        f"during temperature spikes."
    )

    print(
        "[PASS] Temperature spikes did not "
        "trigger temporal adaptation."
    )

    # ========================================================
    # PHASE 5 — TEMPORAL DRIFT
    # ========================================================

    print()
    print(
        "PHASE 5 — SLOW TEMPORAL DRIFT"
    )
    print("-" * 88)

    drift_threshold_before = (
        get_threshold(engine)
    )

    drift_results = process_dataset(
        engine,
        drift_df,
        drift_scores,
    )

    drift_threshold_after = (
        get_threshold(engine)
    )

    drift_temporal = count(
        drift_results,
        "temporal_drift",
    )

    drift_alerts = count(
        drift_results,
        "alert",
    )

    drift_adaptations = count(
        drift_results,
        "adapted",
    )

    phase_summary(
        "Temporal drift",
        drift_results,
    )

    print(
        f"Threshold : "
        f"{drift_threshold_before:.12f}"
        f" -> "
        f"{drift_threshold_after:.12f}"
    )

    print(
        f"Temporal drift signals : "
        f"{drift_temporal}"
    )

    print(
        f"Alerts                 : "
        f"{drift_alerts}"
    )

    print(
        f"Adaptations            : "
        f"{drift_adaptations}"
    )

    assert drift_temporal > 0, (
        f"{model_name}: slow temporal drift "
        f"was not detected."
    )

    assert drift_alerts > 0, (
        f"{model_name}: temporal drift "
        f"did not generate an alert."
    )

    assert np.isclose(
        drift_threshold_after,
        drift_threshold_before,
        rtol=0.0,
        atol=1e-15,
    ), (
        f"{model_name}: threshold changed "
        f"during temporal drift."
    )

    assert drift_adaptations == 0, (
        f"{model_name}: adaptive threshold "
        f"was updated during temporal drift."
    )

    print(
        "[PASS] Temporal drift detected and "
        "adaptive learning remained frozen."
    )

    # ========================================================
    # FINAL STATE
    # ========================================================

    state = engine.get_state()

    print()
    print(
        "FINAL STATE"
    )
    print("-" * 88)

    interesting_keys = (
        "state",
        "current_threshold",
        "threshold",
        "regime_state",
        "alert_count",
        "adaptation_count",
        "regime_change_count",
    )

    printed = set()

    for key in interesting_keys:

        if key in state:
            print(
                f"{key:<25}: {state[key]}"
            )

            printed.add(key)

    # Print only useful state values.
    for key, value in state.items():

        if key in printed:
            continue

        if isinstance(
            value,
            (
                list,
                dict,
            ),
        ):
            continue

        print(
            f"{key:<25}: {value}"
        )

    print(
        f"Final threshold         : "
        f"{get_threshold(engine):.12f}"
    )

    print(
        f"[PASS] {model_name.upper()} "
        f"FULL LIFECYCLE"
    )

    return {
        "model": model_name,
        "initial_threshold": initial_threshold,
        "seasonal_threshold": seasonal_threshold,
        "final_threshold": get_threshold(
            engine
        ),
        "seasonal_confirmed": seasonal_confirmed,
        "seasonal_adaptations": seasonal_adaptations,
        "spike_temporal": spike_temporal,
        "drift_temporal": drift_temporal,
        "drift_alerts": drift_alerts,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 88)
    print(
        "FINAL FULL ADAPTIVE LIFECYCLE INTEGRATION TEST"
    )
    print("=" * 88)

    print()
    print(
        "Lifecycle:"
    )
    print(
        "normal → seasonal → confirmation → "
        "adaptation → stable seasonal → spikes → "
        "temporal drift → frozen"
    )

    print()
    print(
        "MODEL CONFIGURATION"
    )
    print("-" * 88)

    for model_name in MODELS:

        config = MODEL_CONFIG[
            model_name
        ]

        print(
            f"{model_name:<10} "
            f"P{config['percentile']:<5.1f} "
            f"sigma={config['shift_sigma']:<4.2f} "
            f"tolerance={config['stability_tolerance']:<4.2f}"
        )

    # ========================================================
    # LOAD DATA
    # ========================================================

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
    print("-" * 88)

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

    # ========================================================
    # SCORE GENERATION
    # ========================================================

    print()
    print(
        "GENERATING MODEL SCORES"
    )
    print("-" * 88)

    scores = {}

    for model_name in MODELS:

        print(
            f"  {model_name.upper()}..."
        )

        scores[
            model_name
        ] = {
            "calibration": get_scores(
                calibration_df,
                model_name,
            ),
            "seasonal": get_scores(
                seasonal_df,
                model_name,
            ),
            "spikes": get_scores(
                spikes_df,
                model_name,
            ),
            "drift": get_scores(
                drift_df,
                model_name,
            ),
        }

    print(
        "Scores generated."
    )

    # ========================================================
    # RUN MODELS
    # ========================================================

    results = []

    for model_name in MODELS:

        model_scores = scores[
            model_name
        ]

        result = run_model(
            model_name,
            calibration_df,
            model_scores[
                "calibration"
            ],
            seasonal_df,
            model_scores[
                "seasonal"
            ],
            spikes_df,
            model_scores[
                "spikes"
            ],
            drift_df,
            model_scores[
                "drift"
            ],
        )

        results.append(
            result
        )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print()
    print("=" * 88)
    print(
        "FINAL LIFECYCLE SUMMARY"
    )
    print("=" * 88)

    print(
        f"{'MODEL':<10}"
        f"{'CONF':>7}"
        f"{'ADAPT':>8}"
        f"{'SPIKE':>8}"
        f"{'DRIFT':>8}"
        f"{'ALERT':>8}"
        f"{'PASS':>8}"
    )

    print("-" * 88)

    for result in results:

        print(
            f"{result['model']:<10}"
            f"{result['seasonal_confirmed']:>7}"
            f"{result['seasonal_adaptations']:>8}"
            f"{result['spike_temporal']:>8}"
            f"{result['drift_temporal']:>8}"
            f"{result['drift_alerts']:>8}"
            f"{'YES':>8}"
        )

    print()
    print(
        "[PASS] ALL MODEL LIFECYCLE TESTS PASSED."
    )

    print()
    print("=" * 88)
    print(
        "FINAL FULL LIFECYCLE TEST COMPLETED"
    )
    print("=" * 88)


if __name__ == "__main__":
    main()