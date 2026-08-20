"""
Adaptive threshold percentile sweep.

Purpose
-------
Evaluate P97 / P98 / P99 / P99.5 using the validated
model-specific regime lifecycle.

Validated regime configuration:

    IFOREST
        shift_sigma = 1.50
        stability_tolerance = 0.20

    LOF
        shift_sigma = 2.50
        stability_tolerance = 0.30

    OCSVM
        shift_sigma = 2.25
        stability_tolerance = 0.20

Architecture:

    STABLE
        |
        v
    REGIME CHANGE
        |
        v
    TEMPORAL VALIDATION
        |
        +---- CLEAN ----> ACCEPT
        |
        +---- DRIFT ----> DRIFT_LOCKED

The percentile recommendation considers:

    1. Seasonal false-positive reduction
    2. Temporal-drift recall
    3. Temporal-drift F1
    4. Successful regime acceptance
    5. No unsafe threshold changes
    6. No temperature-spike drift
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src.adaptive_engine import AdaptiveEngine
from src.model_loader import get_models


# =====================================================================
# CONFIGURATION
# =====================================================================

FEATURE_NAMES = [
    "temperature",
    "humidity",
    "stock_count",
]

PERCENTILES = [
    97.0,
    98.0,
    99.0,
    99.5,
]


# =====================================================================
# MODEL-SPECIFIC REGIME CONFIGURATION
# =====================================================================

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


# =====================================================================
# PATHS
# =====================================================================

ROOT = (
    Path(__file__).resolve().parent.parent
)

OUTPUT = ROOT / "output"

CALIBRATION_PATH = (
    OUTPUT / "calibration_normal.csv"
)

SEASONAL_PATH = (
    OUTPUT / "test_seasonal_normal.csv"
)

DRIFT_PATH = (
    OUTPUT / "test_temporal_drift.csv"
)

SPIKE_PATH = (
    OUTPUT / "test_temperature_spikes.csv"
)


SEASONAL_SIZE = 5000
DRIFT_SIZE = 5000
SPIKE_SIZE = 5000

ATOL = 1e-12


# =====================================================================
# DATA LOADING
# =====================================================================

def load_csv(path):
    if not path.exists():
        return None

    df = pd.read_csv(path)

    if df.empty:
        raise ValueError(
            f"Dataset is empty: {path}"
        )

    missing = [
        column
        for column in FEATURE_NAMES
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"{path} missing columns: {missing}"
        )

    return df


def load_calibration():
    df = load_csv(
        CALIBRATION_PATH
    )

    if df is None:
        raise FileNotFoundError(
            "Calibration dataset not found: "
            f"{CALIBRATION_PATH}"
        )

    return df


# =====================================================================
# MODEL SCORE GENERATION
# =====================================================================

def get_model_scores(df):
    X = df[
        FEATURE_NAMES
    ].to_numpy()

    models = get_models()

    result = {}

    for name, model in models.items():

        raw = model.score(X)

        scores = -np.asarray(
            raw,
            dtype=float,
        )

        if scores.size == 0:
            raise ValueError(
                f"{name} produced no scores."
            )

        if not np.all(
            np.isfinite(scores)
        ):
            raise ValueError(
                f"{name} produced non-finite scores."
            )

        result[
            str(name).lower()
        ] = scores

    return result


# =====================================================================
# SYNTHETIC FALLBACK DATA
# =====================================================================

def synthetic_seasonal(
    calibration_scores,
    size=SEASONAL_SIZE,
):
    rng = np.random.default_rng(
        20260820
    )

    mean = float(
        np.mean(calibration_scores)
    )

    std = max(
        float(
            np.std(calibration_scores)
        ),
        1e-12,
    )

    return rng.normal(
        mean + 2.5 * std,
        std,
        size,
    )


def synthetic_drift(
    calibration_scores,
    size=DRIFT_SIZE,
):
    rng = np.random.default_rng(
        20260822
    )

    mean = float(
        np.mean(calibration_scores)
    )

    std = max(
        float(
            np.std(calibration_scores)
        ),
        1e-12,
    )

    return rng.normal(
        mean + 2.5 * std,
        std,
        size,
    )


def synthetic_spikes(
    calibration_scores,
    size=SPIKE_SIZE,
):
    rng = np.random.default_rng(
        20260825
    )

    indices = rng.integers(
        0,
        len(calibration_scores),
        size=size,
    )

    return calibration_scores[
        indices
    ]


# =====================================================================
# TEMPERATURE FALLBACK GENERATORS
#
# IMPORTANT:
# These names intentionally do NOT overlap with variables used
# inside main().
# =====================================================================

def generate_stable_temperatures(size):
    rng = np.random.default_rng(
        20260821
    )

    return rng.normal(
        22.0,
        1.0,
        size,
    )


def generate_drift_temperatures(size):
    rng = np.random.default_rng(
        20260823
    )

    x = np.arange(
        size,
        dtype=float,
    )

    return (
        22.0
        + 0.04 * x
        + rng.normal(
            0.0,
            0.15,
            size,
        )
    )


def generate_spike_temperatures(size):
    rng = np.random.default_rng(
        20260824
    )

    values = rng.normal(
        22.0,
        1.0,
        size,
    )

    indices = np.arange(
        100,
        size,
        250,
    )

    values[
        indices
    ] += 12.0

    return values


# =====================================================================
# SCENARIO SCORE SELECTION
# =====================================================================

def scenario_scores(
    model_name,
    calibration_scores,
    dataframe,
    fallback_function,
):
    """
    Use the actual scenario dataset when available.

    Otherwise use the deterministic fallback generator.
    """

    if dataframe is not None:

        scores = get_model_scores(
            dataframe
        )

        return scores[
            model_name
        ]

    return fallback_function(
        calibration_scores
    )


# =====================================================================
# METRICS
# =====================================================================

def metrics(
    y_true,
    y_pred,
):
    y_true = np.asarray(
        y_true,
        dtype=int,
    )

    y_pred = np.asarray(
        y_pred,
        dtype=int,
    )

    tp = int(
        np.sum(
            (y_true == 1)
            & (y_pred == 1)
        )
    )

    tn = int(
        np.sum(
            (y_true == 0)
            & (y_pred == 0)
        )
    )

    fp = int(
        np.sum(
            (y_true == 0)
            & (y_pred == 1)
        )
    )

    fn = int(
        np.sum(
            (y_true == 1)
            & (y_pred == 0)
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
        2.0
        * precision
        * recall
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
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fpr,
    }


# =====================================================================
# FIXED THRESHOLD
# =====================================================================

def fixed_threshold(
    calibration_scores,
    percentile=99.0,
):
    return float(
        np.percentile(
            calibration_scores,
            percentile,
        )
    )


# =====================================================================
# ENGINE
# =====================================================================

def create_engine(
    calibration_scores,
    model_name,
    percentile,
):
    config = MODEL_REGIME_CONFIG[
        model_name
    ]

    engine = AdaptiveEngine(
        baseline_size=100,
        candidate_sizes=[
            10,
            25,
            50,
            100,
            200,
        ],
        shift_sigma=config[
            "shift_sigma"
        ],
        stability_tolerance=config[
            "stability_tolerance"
        ],
        min_stable_blocks=2,
        adaptive_percentile=percentile,
        quarantine_recovery_required=25,
    )

    engine.initialize(
        calibration_scores,
        model_name=model_name,
    )

    return engine


# =====================================================================
# STREAM PROCESSING
# =====================================================================

def process_stream(
    engine,
    scores,
    temperatures,
):
    predictions = []
    thresholds = []

    regime_changes = []
    confirmations = []
    acceptances = []
    drifts = []
    alerts = []
    threshold_changes = []

    previous_threshold = (
        engine.adaptive_threshold
        .get_threshold()
    )

    for index, (
        score,
        temperature,
    ) in enumerate(
        zip(
            scores,
            temperatures,
        )
    ):

        result = engine.process(
            score=float(score),
            temperature=float(
                temperature
            ),
        )

        predictions.append(
            int(
                result.get(
                    "is_anomaly",
                    False,
                )
            )
        )

        threshold = (
            engine.adaptive_threshold
            .get_threshold()
        )

        thresholds.append(
            threshold
        )

        if result.get(
            "regime_changed",
            False,
        ):
            regime_changes.append(
                index
            )

        if result.get(
            "regime_confirmed",
            False,
        ):
            confirmations.append(
                index
            )

        if result.get(
            "regime_accepted",
            False,
        ):
            acceptances.append(
                index
            )

        if result.get(
            "temporal_drift",
            False,
        ):
            drifts.append(
                index
            )

        if result.get(
            "alert",
            False,
        ):
            alerts.append(
                index
            )

        if (
            previous_threshold is not None
            and threshold is not None
            and not np.isclose(
                previous_threshold,
                threshold,
                atol=ATOL,
            )
        ):
            threshold_changes.append(
                index
            )

        previous_threshold = (
            threshold
        )

    return {
        "predictions": np.asarray(
            predictions,
            dtype=int,
        ),
        "thresholds": thresholds,
        "regime_changes": regime_changes,
        "confirmations": confirmations,
        "acceptances": acceptances,
        "drifts": drifts,
        "alerts": alerts,
        "threshold_changes": threshold_changes,
    }


# =====================================================================
# SEASONAL EVALUATION
# =====================================================================

def evaluate_seasonal(
    model_name,
    calibration_scores,
    seasonal_scores,
    seasonal_temperature_values,
    percentile,
):
    fixed = fixed_threshold(
        calibration_scores
    )

    labels = np.zeros(
        len(seasonal_scores),
        dtype=int,
    )

    fixed_predictions = (
        seasonal_scores > fixed
    ).astype(int)

    fixed_result = metrics(
        labels,
        fixed_predictions,
    )

    engine = create_engine(
        calibration_scores,
        model_name,
        percentile,
    )

    run = process_stream(
        engine,
        seasonal_scores,
        seasonal_temperature_values,
    )

    accepted = bool(
        run["acceptances"]
    )

    if not accepted:

        return {
            "accepted": False,
            "fixed_threshold": fixed,
            "fixed_metrics": fixed_result,
            "adaptive_metrics": None,
            "accepted_threshold": None,
            "fpr_reduction": None,
            "run": run,
        }

    acceptance_index = (
        run["acceptances"][0]
    )

    accepted_threshold = (
        run["thresholds"][
            acceptance_index
        ]
    )

    adaptive_predictions = (
        seasonal_scores
        > accepted_threshold
    ).astype(int)

    adaptive_result = metrics(
        labels,
        adaptive_predictions,
    )

    fpr_reduction = (
        (
            fixed_result["fpr"]
            - adaptive_result["fpr"]
        )
        / fixed_result["fpr"]
        * 100.0
        if fixed_result["fpr"] > 0
        else 0.0
    )

    return {
        "accepted": True,
        "fixed_threshold": fixed,
        "fixed_metrics": fixed_result,
        "adaptive_metrics": adaptive_result,
        "accepted_threshold": float(
            accepted_threshold
        ),
        "fpr_reduction": fpr_reduction,
        "run": run,
    }


# =====================================================================
# DRIFT EVALUATION
# =====================================================================

def evaluate_drift(
    model_name,
    calibration_scores,
    drift_scores,
    drift_temperature_values,
    percentile,
):
    fixed = fixed_threshold(
        calibration_scores
    )

    labels = np.ones(
        len(drift_scores),
        dtype=int,
    )

    fixed_predictions = (
        drift_scores > fixed
    ).astype(int)

    fixed_result = metrics(
        labels,
        fixed_predictions,
    )

    engine = create_engine(
        calibration_scores,
        model_name,
        percentile,
    )

    run = process_stream(
        engine,
        drift_scores,
        drift_temperature_values,
    )

    first_drift = (
        run["drifts"][0]
        if run["drifts"]
        else None
    )

    unsafe_changes = []

    if first_drift is not None:

        unsafe_changes = [
            index
            for index in run[
                "threshold_changes"
            ]
            if index <= first_drift
        ]

    adaptive_result = metrics(
        labels,
        run["predictions"],
    )

    return {
        "fixed_metrics": fixed_result,
        "adaptive_metrics": adaptive_result,
        "first_drift": first_drift,
        "drift_detected": bool(
            run["drifts"]
        ),
        "unsafe_changes": unsafe_changes,
        "run": run,
    }


# =====================================================================
# SPIKE EVALUATION
# =====================================================================

def evaluate_spikes(
    model_name,
    calibration_scores,
    spike_scores,
    spike_temperature_values,
    percentile,
):
    engine = create_engine(
        calibration_scores,
        model_name,
        percentile,
    )

    return process_stream(
        engine,
        spike_scores,
        spike_temperature_values,
    )


# =====================================================================
# PERCENTILE QUALITY
# =====================================================================

def percentile_quality(
    row,
):
    """
    Higher is better.

    Weighting:

        40% seasonal FPR reduction
        30% temporal drift recall
        30% temporal drift F1

    The percentile must already have passed the
    safety and lifecycle checks before this score
    is considered.
    """

    reduction = max(
        0.0,
        min(
            100.0,
            row["fpr_reduction"],
        ),
    ) / 100.0

    drift_recall = max(
        0.0,
        min(
            1.0,
            row["drift_recall"],
        ),
    )

    drift_f1 = max(
        0.0,
        min(
            1.0,
            row["drift_f1"],
        ),
    )

    return (
        0.40 * reduction
        + 0.30 * drift_recall
        + 0.30 * drift_f1
    )


# =====================================================================
# MODEL EVALUATION
# =====================================================================

def run_model(
    model_name,
    calibration_scores,
    seasonal_scores,
    seasonal_temperature_values,
    drift_scores,
    drift_temperature_values,
    spike_scores,
    spike_temperature_values,
):
    print()
    print(
        "#" * 88
    )
    print(
        f"MODEL: {model_name.upper()}"
    )
    print(
        "#" * 88
    )

    config = MODEL_REGIME_CONFIG[
        model_name
    ]

    print(
        f"shift_sigma="
        f"{config['shift_sigma']:.2f}  "
        f"stability_tolerance="
        f"{config['stability_tolerance']:.2f}"
    )

    fixed = fixed_threshold(
        calibration_scores
    )

    print(
        f"Fixed P99 threshold="
        f"{fixed:.12f}"
    )

    results = []

    for percentile in PERCENTILES:

        seasonal = evaluate_seasonal(
            model_name,
            calibration_scores,
            seasonal_scores,
            seasonal_temperature_values,
            percentile,
        )

        drift = evaluate_drift(
            model_name,
            calibration_scores,
            drift_scores,
            drift_temperature_values,
            percentile,
        )

        spikes = evaluate_spikes(
            model_name,
            calibration_scores,
            spike_scores,
            spike_temperature_values,
            percentile,
        )

        unsafe = bool(
            drift["unsafe_changes"]
        )

        spike_drift = bool(
            spikes["drifts"]
        )

        spike_alerts = bool(
            spikes["alerts"]
        )

        safe = (
            not unsafe
            and not spike_drift
            and not spike_alerts
        )

        accepted = bool(
            seasonal["accepted"]
        )

        row = {
            "percentile": percentile,
            "accepted": accepted,
            "threshold": (
                seasonal[
                    "accepted_threshold"
                ]
                if accepted
                else None
            ),
            "season_fpr": (
                seasonal[
                    "adaptive_metrics"
                ]["fpr"]
                if accepted
                else None
            ),
            "fpr_reduction": (
                seasonal[
                    "fpr_reduction"
                ]
                if accepted
                else None
            ),
            "drift_recall": drift[
                "adaptive_metrics"
            ]["recall"],
            "drift_f1": drift[
                "adaptive_metrics"
            ]["f1"],
            "drift_detected": drift[
                "drift_detected"
            ],
            "unsafe": unsafe,
            "spike_drift": spike_drift,
            "spike_alerts": spike_alerts,
            "safe": safe,
            "regime_changes": len(
                seasonal[
                    "run"
                ]["regime_changes"]
            ),
            "confirmations": len(
                seasonal[
                    "run"
                ]["confirmations"]
            ),
            "acceptances": len(
                seasonal[
                    "run"
                ]["acceptances"]
            ),
        }

        if (
            accepted
            and safe
            and drift["drift_detected"]
        ):
            row["quality"] = (
                percentile_quality(
                    row
                )
            )
        else:
            row["quality"] = -1.0

        results.append(
            row
        )

        threshold_text = (
            f"{row['threshold']:.9f}"
            if row["threshold"] is not None
            else "N/A"
        )

        print(
            f"P{percentile:<4.1f}"
            f" accept="
            f"{'YES' if accepted else 'NO':<3}"
            f" threshold="
            f"{threshold_text:<14}"
        )

        if accepted:

            print(
                f"    seasonal FPR="
                f"{row['season_fpr']:.4f} "
                f"reduction="
                f"{row['fpr_reduction']:.1f}% "
                f"driftRecall="
                f"{row['drift_recall']:.4f} "
                f"driftF1="
                f"{row['drift_f1']:.4f} "
                f"safe="
                f"{row['safe']}"
            )

        else:

            print(
                f"    regime not accepted "
                f"driftRecall="
                f"{row['drift_recall']:.4f} "
                f"driftF1="
                f"{row['drift_f1']:.4f} "
                f"safe="
                f"{row['safe']}"
            )

        print(
            f"    drift="
            f"{row['drift_detected']} "
            f"unsafeChanges="
            f"{int(unsafe)} "
            f"spikeDrift="
            f"{int(spike_drift)} "
            f"spikeAlerts="
            f"{int(spike_alerts)}"
        )

    return results


# =====================================================================
# SUMMARY
# =====================================================================

def print_summary(
    all_results,
):
    print()
    print(
        "=" * 100
    )
    print(
        "PERCENTILE SWEEP SUMMARY"
    )
    print(
        "=" * 100
    )

    recommendations = {}

    for model_name, rows in (
        all_results.items()
    ):

        print()
        print(
            f"MODEL: {model_name.upper()}"
        )

        print(
            "-" * 100
        )

        print(
            "Pctl  Accept  SeasonFPR  "
            "FPRRed.  DriftRec.  "
            "DriftF1  Safe  Score"
        )

        print(
            "-" * 100
        )

        for row in rows:

            season_fpr = (
                f"{row['season_fpr']:.4f}"
                if row["season_fpr"]
                is not None
                else "N/A"
            )

            reduction = (
                f"{row['fpr_reduction']:.1f}%"
                if row["fpr_reduction"]
                is not None
                else "N/A"
            )

            print(
                f"{row['percentile']:4.1f}  "
                f"{'YES' if row['accepted'] else 'NO':>6}  "
                f"{season_fpr:>9}  "
                f"{reduction:>7}  "
                f"{row['drift_recall']:>9.4f}  "
                f"{row['drift_f1']:>7.4f}  "
                f"{str(row['safe']):>4}  "
                f"{row['quality']:>5.3f}"
            )

        valid = [
            row
            for row in rows
            if row["accepted"]
            and row["safe"]
            and row["drift_detected"]
        ]

        if not valid:

            print()
            print(
                "[WARNING] No percentile passed "
                "all validation requirements."
            )

            continue

        best = max(
            valid,
            key=lambda row: row[
                "quality"
            ],
        )

        recommendations[
            model_name
        ] = best

        print()
        print(
            f"[RECOMMENDED] P"
            f"{best['percentile']:.1f}"
        )

        print(
            f"  threshold     = "
            f"{best['threshold']:.12f}"
        )

        print(
            f"  seasonal FPR  = "
            f"{best['season_fpr']:.4f}"
        )

        print(
            f"  FPR reduction = "
            f"{best['fpr_reduction']:.2f}%"
        )

        print(
            f"  drift recall  = "
            f"{best['drift_recall']:.4f}"
        )

        print(
            f"  drift F1      = "
            f"{best['drift_f1']:.4f}"
        )

        print(
            f"  quality score = "
            f"{best['quality']:.4f}"
        )

    print()
    print(
        "=" * 100
    )
    print(
        "FINAL MODEL-SPECIFIC RECOMMENDATIONS"
    )
    print(
        "=" * 100
    )

    for model_name in (
        "iforest",
        "lof",
        "ocsvm",
    ):

        row = recommendations.get(
            model_name
        )

        if row is None:

            print(
                f"{model_name.upper():<8} "
                "NO SAFE RECOMMENDATION"
            )

            continue

        print(
            f"{model_name.upper():<8} "
            f"P{row['percentile']:.1f}  "
            f"threshold="
            f"{row['threshold']:.12f}  "
            f"seasonFPR="
            f"{row['season_fpr']:.4f}  "
            f"driftF1="
            f"{row['drift_f1']:.4f}"
        )


# =====================================================================
# MAIN
# =====================================================================

def main():

    print(
        "=" * 100
    )

    print(
        "ADAPTIVE THRESHOLD PERCENTILE SWEEP"
    )

    print(
        "=" * 100
    )

    print()
    print(
        "PERCENTILES"
    )

    print(
        "97.0, 98.0, 99.0, 99.5"
    )

    print()
    print(
        "MODEL REGIME CONFIGURATION"
    )

    print(
        "-" * 80
    )

    for model_name, config in (
        MODEL_REGIME_CONFIG.items()
    ):

        print(
            f"{model_name:<8} "
            f"sigma="
            f"{config['shift_sigma']:.2f} "
            f"tolerance="
            f"{config['stability_tolerance']:.2f}"
        )

    calibration_df = (
        load_calibration()
    )

    seasonal_df = load_csv(
        SEASONAL_PATH
    )

    drift_df = load_csv(
        DRIFT_PATH
    )

    spike_df = load_csv(
        SPIKE_PATH
    )

    print()
    print(
        f"Calibration rows : "
        f"{len(calibration_df)}"
    )

    print(
        "Generating model scores..."
    )

    calibration_score_map = (
        get_model_scores(
            calibration_df
        )
    )

    print(
        "Scores generated."
    )

    if seasonal_df is not None:

        print(
            "Seasonal dataset : "
            f"{SEASONAL_PATH.name}"
        )

    else:

        print(
            "Seasonal dataset : "
            "synthetic fallback"
        )

    if drift_df is not None:

        print(
            "Drift dataset    : "
            f"{DRIFT_PATH.name}"
        )

    else:

        print(
            "Drift dataset    : "
            "synthetic fallback"
        )

    if spike_df is not None:

        print(
            "Spike dataset    : "
            f"{SPIKE_PATH.name}"
        )

    else:

        print(
            "Spike dataset    : "
            "synthetic fallback"
        )

    all_results = {}

    # =================================================================
    # MODEL LOOP
    # =================================================================

    for model_name in (
        "iforest",
        "lof",
        "ocsvm",
    ):

        if model_name not in (
            calibration_score_map
        ):

            print(
                f"[WARNING] {model_name} "
                "scores unavailable."
            )

            continue

        calibration_scores = (
            calibration_score_map[
                model_name
            ]
        )

        # -------------------------------------------------------------
        # Scenario scores
        # -------------------------------------------------------------

        seasonal_scores = (
            scenario_scores(
                model_name,
                calibration_scores,
                seasonal_df,
                synthetic_seasonal,
            )
        )

        drift_scores = (
            scenario_scores(
                model_name,
                calibration_scores,
                drift_df,
                synthetic_drift,
            )
        )

        spike_scores = (
            scenario_scores(
                model_name,
                calibration_scores,
                spike_df,
                synthetic_spikes,
            )
        )

        # -------------------------------------------------------------
        # Seasonal temperatures
        # -------------------------------------------------------------

        if seasonal_df is not None:

            seasonal_temperature_values = (
                seasonal_df[
                    "temperature"
                ].to_numpy(
                    dtype=float
                )
            )

        else:

            seasonal_temperature_values = (
                generate_stable_temperatures(
                    len(
                        seasonal_scores
                    )
                )
            )

        # -------------------------------------------------------------
        # Drift temperatures
        # -------------------------------------------------------------

        if drift_df is not None:

            drift_temperature_values = (
                drift_df[
                    "temperature"
                ].to_numpy(
                    dtype=float
                )
            )

        else:

            drift_temperature_values = (
                generate_drift_temperatures(
                    len(
                        drift_scores
                    )
                )
            )

        # -------------------------------------------------------------
        # Spike temperatures
        # -------------------------------------------------------------

        if spike_df is not None:

            spike_temperature_values = (
                spike_df[
                    "temperature"
                ].to_numpy(
                    dtype=float
                )
            )

        else:

            spike_temperature_values = (
                generate_spike_temperatures(
                    len(
                        spike_scores
                    )
                )
            )

        # -------------------------------------------------------------
        # Run model
        # -------------------------------------------------------------

        all_results[
            model_name
        ] = run_model(
            model_name,
            calibration_scores,
            seasonal_scores,
            seasonal_temperature_values,
            drift_scores,
            drift_temperature_values,
            spike_scores,
            spike_temperature_values,
        )

    # =================================================================
    # FINAL SUMMARY
    # =================================================================

    print_summary(
        all_results
    )

    print()
    print(
        "=" * 100
    )

    print(
        "ADAPTIVE THRESHOLD PERCENTILE SWEEP COMPLETED"
    )

    print(
        "=" * 100
    )


if __name__ == "__main__":
    main()