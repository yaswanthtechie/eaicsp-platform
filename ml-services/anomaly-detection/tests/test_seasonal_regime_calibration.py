import pandas as pd
import numpy as np

from src.model_loader import (
    feature_names,
    get_models,
)


CALIBRATION = "output/calibration_normal.csv"
SEASONAL = "output/test_seasonal_normal.csv"
SPIKES = "output/test_temperature_spike.csv"


# Number of initial seasonal samples used to establish
# the new operating regime.
REGIME_SIZES = [
    25,
    50,
    100,
    200,
    500,
    1000,
]


PERCENTILE = 99.0


def calculate_metrics(
    scores,
    threshold,
    actual,
):
    predictions = (
        scores > threshold
    ).astype(int)

    actual = np.asarray(actual)

    tp = int(
        ((predictions == 1) & (actual == 1)).sum()
    )

    tn = int(
        ((predictions == 0) & (actual == 0)).sum()
    )

    fp = int(
        ((predictions == 1) & (actual == 0)).sum()
    )

    fn = int(
        ((predictions == 0) & (actual == 1)).sum()
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
        2 * precision * recall
        / (precision + recall)
        if precision + recall > 0
        else 0.0
    )

    return {
        "TP": tp,
        "TN": tn,
        "FP": fp,
        "FN": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def main():

    print("=" * 90)
    print("SEASONAL REGIME CALIBRATION TEST")
    print("=" * 90)

    # --------------------------------------------------------
    # Load datasets
    # --------------------------------------------------------

    calibration_df = pd.read_csv(
        CALIBRATION
    )

    seasonal_df = pd.read_csv(
        SEASONAL
    )

    spike_df = pd.read_csv(
        SPIKES
    )

    calibration_X = (
        calibration_df[
            feature_names
        ].to_numpy()
    )

    seasonal_X = (
        seasonal_df[
            feature_names
        ].to_numpy()
    )

    spike_X = (
        spike_df[
            feature_names
        ].to_numpy()
    )

    seasonal_actual = (
        seasonal_df["is_anomaly"]
        .astype(int)
        .to_numpy()
    )

    spike_actual = (
        spike_df["is_anomaly"]
        .astype(int)
        .to_numpy()
    )

    models = get_models()

    print()
    print(
        f"Calibration samples : {len(calibration_df)}"
    )

    print(
        f"Seasonal samples    : {len(seasonal_df)}"
    )

    print(
        f"Spike samples       : {len(spike_df)}"
    )

    print(
        f"Seasonal anomalies  : {seasonal_actual.sum()}"
    )

    print(
        f"Spike anomalies     : {spike_actual.sum()}"
    )

    # --------------------------------------------------------
    # Test every model
    # --------------------------------------------------------

    for model_name, model in models.items():

        print()
        print("=" * 90)
        print(model_name.upper())
        print("=" * 90)

        # ----------------------------------------------------
        # Scores
        # ----------------------------------------------------

        calibration_scores = (
            -model.score(
                calibration_X
            )
        )

        seasonal_scores = (
            -model.score(
                seasonal_X
            )
        )

        spike_scores = (
            -model.score(
                spike_X
            )
        )

        # ----------------------------------------------------
        # Original calibration threshold
        # ----------------------------------------------------

        calibration_threshold = float(
            np.percentile(
                calibration_scores,
                PERCENTILE,
            )
        )

        print()
        print("ORIGINAL CALIBRATION")
        print("-" * 90)

        print(
            f"P{PERCENTILE:.0f} threshold : "
            f"{calibration_threshold:.6f}"
        )

        seasonal_fixed = calculate_metrics(
            seasonal_scores,
            calibration_threshold,
            seasonal_actual,
        )

        spike_fixed = calculate_metrics(
            spike_scores,
            calibration_threshold,
            spike_actual,
        )

        print(
            f"Seasonal false positives : "
            f"{seasonal_fixed['FP']}"
        )

        print(
            f"Seasonal FPR             : "
            f"{seasonal_fixed['FP'] / len(seasonal_df):.4f}"
        )

        print(
            f"Spike TP                 : "
            f"{spike_fixed['TP']}"
        )

        print(
            f"Spike FN                 : "
            f"{spike_fixed['FN']}"
        )

        # ----------------------------------------------------
        # Regime calibration experiments
        # ----------------------------------------------------

        print()
        print("NEW REGIME CALIBRATION")
        print("-" * 90)

        print(
            "Samples    Threshold       "
            "Seasonal FP     Seasonal FPR     "
            "Spike TP     Spike FN"
        )

        print("-" * 90)

        for regime_size in REGIME_SIZES:

            regime_scores = seasonal_scores[
                :regime_size
            ]

            regime_threshold = float(
                np.percentile(
                    regime_scores,
                    PERCENTILE,
                )
            )

            seasonal_metrics = calculate_metrics(
                seasonal_scores,
                regime_threshold,
                seasonal_actual,
            )

            spike_metrics = calculate_metrics(
                spike_scores,
                regime_threshold,
                spike_actual,
            )

            seasonal_fpr = (
                seasonal_metrics["FP"]
                / len(seasonal_df)
            )

            print(
                f"{regime_size:<10} "
                f"{regime_threshold:>12.6f}   "
                f"{seasonal_metrics['FP']:>10}   "
                f"{seasonal_fpr:>12.4f}   "
                f"{spike_metrics['TP']:>10}   "
                f"{spike_metrics['FN']:>8}"
            )

        # ----------------------------------------------------
        # Ideal seasonal threshold
        # ----------------------------------------------------

        seasonal_threshold = float(
            np.percentile(
                seasonal_scores,
                PERCENTILE,
            )
        )

        seasonal_metrics = calculate_metrics(
            seasonal_scores,
            seasonal_threshold,
            seasonal_actual,
        )

        spike_metrics = calculate_metrics(
            spike_scores,
            seasonal_threshold,
            spike_actual,
        )

        print()
        print("IDEAL NEW-REGIME THRESHOLD")
        print("-" * 90)

        print(
            f"Seasonal P99 threshold : "
            f"{seasonal_threshold:.6f}"
        )

        print(
            f"Seasonal FP           : "
            f"{seasonal_metrics['FP']}"
        )

        print(
            f"Seasonal FPR          : "
            f"{seasonal_metrics['FP'] / len(seasonal_df):.4f}"
        )

        print(
            f"Spike TP              : "
            f"{spike_metrics['TP']}"
        )

        print(
            f"Spike FN              : "
            f"{spike_metrics['FN']}"
        )

        # ----------------------------------------------------
        # Interpretation
        # ----------------------------------------------------

        print()
        print("INTERPRETATION")
        print("-" * 90)

        if (
            seasonal_metrics["FP"]
            < seasonal_fixed["FP"]
            and spike_metrics["TP"]
            == spike_fixed["TP"]
        ):

            print(
                "[PASS] A new seasonal regime can "
                "reduce false positives without "
                "losing spike detections."
            )

        else:

            print(
                "[INFO] The new-regime threshold does "
                "not preserve the original detection "
                "performance for this model."
            )

    print()
    print("=" * 90)
    print("TEST COMPLETED")
    print("=" * 90)


if __name__ == "__main__":
    main()