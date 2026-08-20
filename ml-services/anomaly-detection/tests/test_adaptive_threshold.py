from pathlib import Path

import numpy as np
import pandas as pd

from src.adaptive_threshold import AdaptiveThreshold
from src.model_loader import (
    feature_names,
    get_models,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"

CALIBRATION = OUTPUT_DIR / "calibration_normal.csv"
SEASONAL = OUTPUT_DIR / "test_seasonal_normal.csv"
SPIKES = OUTPUT_DIR / "test_temperature_spike.csv"

WINDOW_SIZE = 50
PERCENTILE = 99.0

MODEL_NAMES = [
    "iforest",
    "lof",
    "ocsvm",
]


# ============================================================
# DATA
# ============================================================

def load_dataset(path):
    df = pd.read_csv(path)

    required = set(
        feature_names
        + ["is_anomaly"]
    )

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"{path} is missing columns: "
            f"{sorted(missing)}"
        )

    return df


# ============================================================
# MODEL SCORING
# ============================================================

def score_dataset(
    df,
    model_name,
):
    """
    Generate the project's normalized anomaly scores.

    Existing project convention:

        raw_score = model.score(...)
        anomaly_score = -raw_score

    Therefore:

        higher anomaly_score = more anomalous

    SHAP is deliberately not used here because this test
    evaluates AdaptiveThreshold, not explainability.
    """

    models = get_models()

    if model_name not in models:
        raise ValueError(
            f"Unknown model: {model_name}"
        )

    model = models[model_name]

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

    if len(raw_scores) != len(df):
        raise ValueError(
            f"{model_name} returned "
            f"{len(raw_scores)} scores for "
            f"{len(df)} rows."
        )

    if not np.all(
        np.isfinite(raw_scores)
    ):
        raise ValueError(
            f"{model_name} produced "
            "non-finite raw scores."
        )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # This matches src.predict._get_prediction_details()
    #
    # raw_score:
    #     higher = more normal
    #
    # anomaly_score:
    #     higher = more anomalous
    # --------------------------------------------------------

    anomaly_scores = -raw_scores

    return anomaly_scores


# ============================================================
# CLASSIFICATION
# ============================================================

def classify(
    manager,
    scores,
):
    predictions = []

    for score in scores:

        is_anomaly, _ = (
            manager.is_anomaly(
                score
            )
        )

        predictions.append(
            bool(is_anomaly)
        )

    return np.asarray(
        predictions,
        dtype=bool,
    )


# ============================================================
# METRICS
# ============================================================

def confusion_matrix(
    actual,
    predicted,
):
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

    print()
    print(name)
    print("-" * 80)

    print(
        f"TP        : {tp}"
    )

    print(
        f"TN        : {tn}"
    )

    print(
        f"FP        : {fp}"
    )

    print(
        f"FN        : {fn}"
    )

    print(
        f"FPR       : {fpr:.4f}"
    )

    print(
        f"Precision : {precision:.4f}"
    )

    print(
        f"Recall    : {recall:.4f}"
    )

    print(
        f"F1        : {f1:.4f}"
    )

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
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print(
        "ADAPTIVE THRESHOLD MODEL INTEGRATION TEST"
    )
    print("=" * 80)

    print()
    print(
        "Raw model scores are generated directly "
        "from the loaded models."
    )

    print(
        "SHAP explanations are intentionally bypassed."
    )

    print()
    print(
        "Score convention:"
    )

    print(
        "raw_score -> anomaly_score = -raw_score"
    )

    print(
        "Higher anomaly_score = more anomalous"
    )

    print()
    print(
        f"Window size : {WINDOW_SIZE}"
    )

    print(
        f"Percentile  : {PERCENTILE}"
    )

    # ========================================================
    # Load datasets
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

    # ========================================================
    # Models
    # ========================================================

    for model_name in MODEL_NAMES:

        print()
        print("=" * 80)

        print(
            f"{model_name.upper()} — "
            "ADAPTIVE THRESHOLD"
        )

        print("=" * 80)

        # ----------------------------------------------------
        # Generate scores
        # ----------------------------------------------------

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

        print(
            "Scores generated."
        )

        # ----------------------------------------------------
        # Score distributions
        # ----------------------------------------------------

        print()
        print(
            "SCORE DISTRIBUTIONS"
        )
        print("-" * 80)

        print(
            f"Calibration P95 : "
            f"{np.percentile(calibration_scores, 95):.6f}"
        )

        print(
            f"Calibration P99 : "
            f"{np.percentile(calibration_scores, 99):.6f}"
        )

        print(
            f"Seasonal P95   : "
            f"{np.percentile(seasonal_scores, 95):.6f}"
        )

        print(
            f"Seasonal P99   : "
            f"{np.percentile(seasonal_scores, 99):.6f}"
        )

        print(
            f"Spike P95      : "
            f"{np.percentile(spike_scores, 95):.6f}"
        )

        print(
            f"Spike P99      : "
            f"{np.percentile(spike_scores, 99):.6f}"
        )

        # ----------------------------------------------------
        # Initialize threshold
        # ----------------------------------------------------

        manager = AdaptiveThreshold(
            window_size=WINDOW_SIZE,
            percentile=PERCENTILE,
        )

        manager.initialize(
            calibration_scores
        )

        initial_threshold = (
            manager.get_threshold()
        )

        print()
        print(
            "INITIAL CALIBRATION"
        )
        print("-" * 80)

        print(
            f"Initial threshold : "
            f"{initial_threshold:.6f}"
        )

        # ----------------------------------------------------
        # Original calibration
        # ----------------------------------------------------

        calibration_pred = classify(
            manager,
            calibration_scores,
        )

        print_metrics(
            "ORIGINAL CALIBRATION",
            calibration_df[
                "is_anomaly"
            ].to_numpy(),
            calibration_pred,
        )

        # ----------------------------------------------------
        # Seasonal before adaptation
        # ----------------------------------------------------

        seasonal_pred_before = classify(
            manager,
            seasonal_scores,
        )

        print_metrics(
            "SEASONAL NORMAL — BEFORE ADAPTATION",
            seasonal_df[
                "is_anomaly"
            ].to_numpy(),
            seasonal_pred_before,
        )

        # ----------------------------------------------------
        # Controlled regime adaptation
        #
        # test_seasonal_normal.csv is known normal data.
        #
        # Therefore, for this controlled test only, all
        # seasonal scores are considered trusted-normal scores.
        # ----------------------------------------------------

        manager.reset()

        manager.initialize(
            calibration_scores
        )

        for score in seasonal_scores:

            manager.update(
                score
            )

        adaptive_threshold = (
            manager.get_threshold()
        )

        print()
        print(
            "SEASONAL ADAPTATION"
        )
        print("-" * 80)

        print(
            f"Initial threshold  : "
            f"{initial_threshold:.6f}"
        )

        print(
            f"Adaptive threshold : "
            f"{adaptive_threshold:.6f}"
        )

        print(
            f"Threshold movement : "
            f"{adaptive_threshold - initial_threshold:.6f}"
        )

        # ----------------------------------------------------
        # Seasonal after adaptation
        # ----------------------------------------------------

        seasonal_pred_after = classify(
            manager,
            seasonal_scores,
        )

        print_metrics(
            "SEASONAL NORMAL — AFTER ADAPTATION",
            seasonal_df[
                "is_anomaly"
            ].to_numpy(),
            seasonal_pred_after,
        )

        # ----------------------------------------------------
        # Temperature spikes
        # ----------------------------------------------------

        spike_pred = classify(
            manager,
            spike_scores,
        )

        print_metrics(
            "TEMPERATURE SPIKES — AFTER ADAPTATION",
            spikes_df[
                "is_anomaly"
            ].to_numpy(),
            spike_pred,
        )

        # ----------------------------------------------------
        # Final state
        # ----------------------------------------------------

        print()
        print(
            "FINAL ADAPTIVE STATE"
        )
        print("-" * 80)

        state = manager.get_state()

        for key, value in state.items():

            print(
                f"{key:<25}: {value}"
            )

    print()
    print("=" * 80)
    print(
        "TEST COMPLETED"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()