import pandas as pd

from sklearn.metrics import (
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
)

from src.adaptive_threshold import (
    AdaptiveThreshold,
)

from src.model_loader import (
    feature_names,
    get_models,
)


SEASONAL_DATASET = (
    "output/test_seasonal_normal.csv"
)

SPIKE_DATASET = (
    "output/test_temperature_spike.csv"
)

BACKGROUND = (
    "models/background_sample.csv"
)


WINDOW_SIZE = 100
PERCENTILE = 99.0


def calculate_metrics(
    actual,
    predicted,
):
    """
    Calculate binary anomaly-detection metrics.
    """

    tn, fp, fn, tp = (
        confusion_matrix(
            actual,
            predicted,
            labels=[0, 1],
        ).ravel()
    )

    return {
        "TP": int(tp),
        "TN": int(tn),
        "FP": int(fp),
        "FN": int(fn),
        "precision": precision_score(
            actual,
            predicted,
            zero_division=0,
        ),
        "recall": recall_score(
            actual,
            predicted,
            zero_division=0,
        ),
        "f1": f1_score(
            actual,
            predicted,
            zero_division=0,
        ),
    }


def evaluate_model(
    model_name,
    model,
    background_df,
    seasonal_df,
    spike_df,
):
    """
    Evaluate fixed and adaptive behavior.

    Sequence:

        1. Calibration background
        2. Seasonal normal regime
        3. Temperature spike anomalies

    The adaptive baseline is initialized only from the
    trusted calibration-normal data.

    During the seasonal phase, only readings classified
    as normal are allowed to update the baseline.

    During the spike phase, anomalous readings are never
    added to the baseline.
    """

    # --------------------------------------------------------
    # Prepare feature matrices
    # --------------------------------------------------------

    background_X = (
        background_df[
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

    # --------------------------------------------------------
    # Initialize adaptive baseline
    # from calibration-normal data
    # --------------------------------------------------------

    background_scores = (
        -model.score(
            background_X
        )
    )

    threshold_manager = (
        AdaptiveThreshold(
            window_size=WINDOW_SIZE,
            percentile=PERCENTILE,
        )
    )

    threshold_manager.initialize(
        background_scores
    )

    initial_threshold = (
        threshold_manager.get_threshold()
    )

    # --------------------------------------------------------
    # FIXED MODEL
    #
    # Native model.predict() uses the model's existing
    # fixed decision boundary.
    # --------------------------------------------------------

    seasonal_fixed = (
        model.predict(
            seasonal_X
        ) == -1
    ).astype(int)

    spike_fixed = (
        model.predict(
            spike_X
        ) == -1
    ).astype(int)

    # --------------------------------------------------------
    # ADAPTIVE MODEL
    #
    # First process the legitimate seasonal shift.
    # --------------------------------------------------------

    seasonal_scores = (
        -model.score(
            seasonal_X
        )
    )

    seasonal_adaptive = []

    seasonal_thresholds = []

    for score in seasonal_scores:

        is_anomaly, threshold = (
            threshold_manager.is_anomaly(
                score
            )
        )

        seasonal_adaptive.append(
            int(is_anomaly)
        )

        seasonal_thresholds.append(
            threshold
        )

        # Only trusted normal observations
        # are allowed to update the baseline.

        if not is_anomaly:

            threshold_manager.update(
                score
            )

    seasonal_adaptive = (
        pd.Series(
            seasonal_adaptive
        )
        .astype(int)
        .to_numpy()
    )

    # Threshold immediately after
    # seasonal adaptation.

    seasonal_threshold = (
        threshold_manager.get_threshold()
    )

    # --------------------------------------------------------
    # ADAPTIVE MODEL
    #
    # Now evaluate actual temperature spikes.
    # --------------------------------------------------------

    spike_scores = (
        -model.score(
            spike_X
        )
    )

    spike_adaptive = []

    spike_thresholds = []

    for score in spike_scores:

        is_anomaly, threshold = (
            threshold_manager.is_anomaly(
                score
            )
        )

        spike_adaptive.append(
            int(is_anomaly)
        )

        spike_thresholds.append(
            threshold
        )

        # IMPORTANT:
        #
        # Do NOT update the baseline with anomalies.
        #
        # If a spike is normal according to the
        # adaptive threshold, it is technically
        # eligible for update. We deliberately prevent
        # that here because this phase contains the
        # known anomaly dataset.
        #
        # This keeps the spike evaluation from
        # contaminating the baseline.

    spike_adaptive = (
        pd.Series(
            spike_adaptive
        )
        .astype(int)
        .to_numpy()
    )

    final_threshold = (
        threshold_manager.get_threshold()
    )

    # --------------------------------------------------------
    # Actual labels
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    seasonal_fixed_metrics = (
        calculate_metrics(
            seasonal_actual,
            seasonal_fixed,
        )
    )

    seasonal_adaptive_metrics = (
        calculate_metrics(
            seasonal_actual,
            seasonal_adaptive,
        )
    )

    spike_fixed_metrics = (
        calculate_metrics(
            spike_actual,
            spike_fixed,
        )
    )

    spike_adaptive_metrics = (
        calculate_metrics(
            spike_actual,
            spike_adaptive,
        )
    )

    return {
        "initial_threshold": initial_threshold,
        "seasonal_threshold": seasonal_threshold,
        "final_threshold": final_threshold,

        "seasonal_threshold_min": min(
            seasonal_thresholds
        ),

        "seasonal_threshold_max": max(
            seasonal_thresholds
        ),

        "spike_threshold_min": min(
            spike_thresholds
        ),

        "spike_threshold_max": max(
            spike_thresholds
        ),

        "seasonal_fixed": (
            seasonal_fixed_metrics
        ),

        "seasonal_adaptive": (
            seasonal_adaptive_metrics
        ),

        "spike_fixed": (
            spike_fixed_metrics
        ),

        "spike_adaptive": (
            spike_adaptive_metrics
        ),
    }


def print_metrics(
    title,
    metrics,
):
    """
    Print detection metrics.
    """

    print()
    print(title)
    print("-" * 80)

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


def main():

    print("=" * 80)
    print(
        "R4 SEQUENTIAL ADAPTIVE SEASONAL SHIFT TEST"
    )
    print("=" * 80)

    # --------------------------------------------------------
    # Load datasets
    # --------------------------------------------------------

    background_df = pd.read_csv(
        BACKGROUND
    )

    seasonal_df = pd.read_csv(
        SEASONAL_DATASET
    )

    spike_df = pd.read_csv(
        SPIKE_DATASET
    )

    models = get_models()

    print()
    print("DATASETS")
    print("-" * 80)

    print(
        f"Calibration samples : "
        f"{len(background_df)}"
    )

    print(
        f"Seasonal samples    : "
        f"{len(seasonal_df)}"
    )

    print(
        f"Spike samples       : "
        f"{len(spike_df)}"
    )

    print(
        f"Seasonal anomalies  : "
        f"{seasonal_df['is_anomaly'].sum()}"
    )

    print(
        f"Spike anomalies     : "
        f"{spike_df['is_anomaly'].sum()}"
    )

    print()
    print(
        f"Adaptive window     : "
        f"{WINDOW_SIZE}"
    )

    print(
        f"Adaptive percentile : "
        f"{PERCENTILE}"
    )

    # --------------------------------------------------------
    # Evaluate every model
    # --------------------------------------------------------

    for model_name, model in models.items():

        result = evaluate_model(
            model_name=model_name,
            model=model,
            background_df=background_df,
            seasonal_df=seasonal_df,
            spike_df=spike_df,
        )

        print()
        print("=" * 80)
        print(
            model_name.upper()
        )
        print("=" * 80)

        # ----------------------------------------------------
        # Threshold movement
        # ----------------------------------------------------

        print()
        print("THRESHOLD MOVEMENT")
        print("-" * 80)

        print(
            f"Initial calibration : "
            f"{result['initial_threshold']:.6f}"
        )

        print(
            f"After seasonal shift: "
            f"{result['seasonal_threshold']:.6f}"
        )

        print(
            f"Final threshold     : "
            f"{result['final_threshold']:.6f}"
        )

        # ----------------------------------------------------
        # Seasonal fixed
        # ----------------------------------------------------

        print_metrics(
            "FIXED MODEL — SEASONAL NORMAL",
            result["seasonal_fixed"],
        )

        # ----------------------------------------------------
        # Seasonal adaptive
        # ----------------------------------------------------

        print_metrics(
            "ADAPTIVE MODEL — SEASONAL NORMAL",
            result["seasonal_adaptive"],
        )

        # ----------------------------------------------------
        # Spike fixed
        # ----------------------------------------------------

        print_metrics(
            "FIXED MODEL — TEMPERATURE SPIKES",
            result["spike_fixed"],
        )

        # ----------------------------------------------------
        # Spike adaptive
        # ----------------------------------------------------

        print_metrics(
            "ADAPTIVE MODEL — TEMPERATURE SPIKES",
            result["spike_adaptive"],
        )

        # ----------------------------------------------------
        # Interpretation
        # ----------------------------------------------------

        fixed_fp = (
            result[
                "seasonal_fixed"
            ]["FP"]
        )

        adaptive_fp = (
            result[
                "seasonal_adaptive"
            ]["FP"]
        )

        adaptive_tp = (
            result[
                "spike_adaptive"
            ]["TP"]
        )

        adaptive_fn = (
            result[
                "spike_adaptive"
            ]["FN"]
        )

        print()
        print("R4 INTERPRETATION")
        print("-" * 80)

        print(
            f"Seasonal fixed FP    : "
            f"{fixed_fp}"
        )

        print(
            f"Seasonal adaptive FP : "
            f"{adaptive_fp}"
        )

        print(
            f"Spike adaptive TP    : "
            f"{adaptive_tp}"
        )

        print(
            f"Spike adaptive FN    : "
            f"{adaptive_fn}"
        )

        if adaptive_fp < fixed_fp:

            print(
                "[PASS] Adaptive threshold "
                "reduced seasonal false positives."
            )

        else:

            print(
                "[INFO] Adaptive threshold "
                "did not reduce seasonal false positives."
            )

        if adaptive_fn == 0:

            print(
                "[PASS] Adaptive threshold "
                "detected all spike anomalies."
            )

        else:

            print(
                "[WARNING] Adaptive threshold "
                "missed some spike anomalies."
            )

    print()
    print("=" * 80)
    print("TEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()