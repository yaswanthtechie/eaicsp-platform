from pathlib import Path

import numpy as np
import pandas as pd

from .model_loader import (
    feature_names,
    get_models,
)

from .regime_detector import (
    RegimeDetector,
)


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)

OUTPUT_DIR = PROJECT_ROOT / "output"

CALIBRATION_DATASET = (
    OUTPUT_DIR / "calibration_normal.csv"
)

SEASONAL_DATASET = (
    OUTPUT_DIR / "test_seasonal_normal.csv"
)


# ============================================================
# COMMON CONFIGURATION
# ============================================================

BASELINE_SIZE = 100

CANDIDATE_SIZES = [
    10,
    25,
    50,
    100,
    200,
]

MIN_STABLE_BLOCKS = 2


# ============================================================
# MODEL-SPECIFIC CONFIGURATION
#
# LOF is deliberately given a wider stability tolerance
# because the previous calibration showed:
#
#     strong shift
#     but only 1 stable checkpoint
#
# We therefore do NOT simply lower shift_sigma.
#
# ------------------------------------------------------------
#
# IFOREST:
#     stability_tolerance = 0.20
#
# LOF:
#     stability_tolerance = 0.30
#
# OCSVM:
#     stability_tolerance = 0.20
#
# These values are calibration candidates.
# They are NOT automatically production settings.
# ============================================================

MODEL_CONFIG = {

    "iforest": {
        "stability_tolerance": 0.20,
        "shift_sigma_sweep": [
            1.00,
            1.25,
            1.50,
            1.75,
            2.00,
            2.25,
            2.50,
        ],
    },

    "lof": {
        "stability_tolerance": 0.30,
        "shift_sigma_sweep": [
            1.50,
            1.75,
            2.00,
            2.25,
            2.50,
            2.75,
            3.00,
            3.25,
            3.50,
            3.75,
            4.00,
            4.25,
            4.50,
        ],
    },

    "ocsvm": {
        "stability_tolerance": 0.20,
        "shift_sigma_sweep": [
            1.50,
            1.75,
            2.00,
            2.25,
            2.50,
            2.75,
            3.00,
        ],
    },
}


DEFAULT_CONFIG = {
    "stability_tolerance": 0.20,
    "shift_sigma_sweep": [
        1.50,
        2.00,
        2.50,
        3.00,
    ],
}


# ============================================================
# SCORE CALCULATION
# ============================================================

def calculate_scores(
    df: pd.DataFrame,
    model,
) -> np.ndarray:
    """
    Project convention:

        anomaly_score = -model.score(...)

    Higher score means more anomalous.
    """

    missing = [
        name
        for name in feature_names
        if name not in df.columns
    ]

    if missing:
        raise ValueError(
            "Dataset is missing required "
            f"features: {missing}"
        )

    X = df[
        feature_names
    ].to_numpy()

    raw_scores = model.score(X)

    scores = -np.asarray(
        raw_scores,
        dtype=float,
    )

    scores = scores[
        np.isfinite(scores)
    ]

    if scores.size == 0:
        raise ValueError(
            "No valid scores were generated."
        )

    return scores


# ============================================================
# STATISTICS
# ============================================================

def calculate_statistics(scores):

    values = np.asarray(
        scores,
        dtype=float,
    )

    values = values[
        np.isfinite(values)
    ]

    if values.size == 0:
        return {
            "samples": 0,
            "mean": None,
            "std": None,
            "median": None,
            "mad": None,
            "p99": None,
        }

    median = float(
        np.median(values)
    )

    mad = float(
        np.median(
            np.abs(
                values - median
            )
        )
    )

    return {
        "samples": int(
            values.size
        ),
        "mean": float(
            np.mean(values)
        ),
        "std": float(
            np.std(values)
        ),
        "median": median,
        "mad": mad,
        "p99": float(
            np.percentile(
                values,
                99,
            )
        ),
    }


def fmt(
    value,
    digits=6,
):

    if value is None:
        return "-"

    return f"{float(value):.{digits}f}"


# ============================================================
# MODEL CONFIG
# ============================================================

def get_model_config(
    model_name,
):

    return MODEL_CONFIG.get(
        str(model_name).lower(),
        DEFAULT_CONFIG,
    )


# ============================================================
# DETECTOR CREATION
# ============================================================

def create_detector(
    baseline_scores,
    model_name,
    shift_sigma,
):
    """
    Create a model-specific regime detector.

    Important:

    The model name controls configuration only.
    RegimeDetector itself remains model agnostic.
    """

    config = get_model_config(
        model_name
    )

    detector = RegimeDetector(
        candidate_sizes=CANDIDATE_SIZES,
        baseline_size=BASELINE_SIZE,
        shift_sigma=float(
            shift_sigma
        ),
        stability_tolerance=float(
            config[
                "stability_tolerance"
            ]
        ),
        min_stable_blocks=(
            MIN_STABLE_BLOCKS
        ),
    )

    detector.initialize(
        baseline_scores
    )

    return detector


# ============================================================
# SINGLE CALIBRATION RUN
# ============================================================

def evaluate_shift_sigma(
    calibration_scores,
    regime_scores,
    model_name,
    shift_sigma,
):
    """
    Evaluate one model with one shift_sigma.

    No adaptive threshold is changed here.

    This tests ONLY regime detection.
    """

    detector = create_detector(
        calibration_scores,
        model_name,
        shift_sigma,
    )

    confirmation_index = None
    confirmed_scores = []

    max_shift_strength = 0.0
    final_shift_strength = 0.0

    max_stable_blocks = 0
    final_stable_blocks = 0

    max_stage = -1

    observations = 0

    for index, score in enumerate(
        regime_scores
    ):

        observations += 1

        result = detector.observe(
            float(score)
        )

        shift_strength = float(
            result.get(
                "shift_strength",
                0.0,
            )
        )

        max_shift_strength = max(
            max_shift_strength,
            shift_strength,
        )

        final_shift_strength = (
            shift_strength
        )

        stable_blocks = int(
            result.get(
                "stable_blocks",
                0,
            )
        )

        max_stable_blocks = max(
            max_stable_blocks,
            stable_blocks,
        )

        final_stable_blocks = (
            stable_blocks
        )

        stage = result.get(
            "stage",
            -1,
        )

        if stage is not None:
            max_stage = max(
                max_stage,
                int(stage),
            )

        if (
            result.get(
                "regime_confirmed",
                False,
            )
            and confirmation_index is None
        ):

            confirmation_index = index

            confirmed_scores = (
                detector.get_confirmed_scores()
            )

            break

    accepted = False

    if confirmed_scores:

        detector.accept_regime(
            confirmed_scores
        )

        accepted = True

    state = detector.get_state()

    return {
        "shift_sigma": float(
            shift_sigma
        ),
        "detected": (
            confirmation_index
            is not None
        ),
        "confirmation_index": (
            confirmation_index
        ),
        "confirmed_samples": int(
            len(
                confirmed_scores
            )
        ),
        "accepted": bool(
            accepted
        ),
        "max_shift_strength": (
            max_shift_strength
        ),
        "final_shift_strength": (
            final_shift_strength
        ),
        "max_stable_blocks": (
            max_stable_blocks
        ),
        "final_stable_blocks": (
            final_stable_blocks
        ),
        "max_stage": int(
            max_stage
        ),
        "observations_used": int(
            observations
        ),
        "final_candidate_size": int(
            state.get(
                "candidate_sample_count",
                0,
            )
        ),
    }


# ============================================================
# MODEL SWEEP
# ============================================================

def calibrate_model(
    model_name,
    calibration_scores,
    regime_scores,
):

    config = get_model_config(
        model_name
    )

    results = []

    for shift_sigma in (
        config[
            "shift_sigma_sweep"
        ]
    ):

        result = evaluate_shift_sigma(
            calibration_scores,
            regime_scores,
            model_name,
            shift_sigma,
        )

        results.append(
            result
        )

    return results


# ============================================================
# SUCCESSFUL CANDIDATES
# ============================================================

def successful_results(
    results,
):

    return [
        result
        for result in results
        if (
            result["detected"]
            and result["accepted"]
        )
    ]


def summarize_candidates(
    results,
):

    successful = successful_results(
        results
    )

    if not successful:
        return {
            "lowest": None,
            "highest": None,
            "recommended": None,
        }

    lowest = min(
        successful,
        key=lambda item:
        item["shift_sigma"],
    )

    highest = max(
        successful,
        key=lambda item:
        item["shift_sigma"],
    )

    # --------------------------------------------------------
    # Recommended calibration candidate
    #
    # Prefer the middle of the successful range rather than
    # automatically choosing the lowest threshold.
    #
    # This avoids making the detector unnecessarily sensitive.
    # --------------------------------------------------------

    successful_sorted = sorted(
        successful,
        key=lambda item:
        item["shift_sigma"],
    )

    recommended = successful_sorted[
        len(successful_sorted) // 2
    ]

    return {
        "lowest": lowest,
        "highest": highest,
        "recommended": recommended,
    }


# ============================================================
# PRINT DISTRIBUTION
# ============================================================

def print_statistics(
    title,
    statistics,
):

    print()
    print(title)
    print("-" * 60)

    print(
        f"Samples       : "
        f"{statistics['samples']}"
    )

    print(
        f"Mean          : "
        f"{fmt(statistics['mean'])}"
    )

    print(
        f"Std           : "
        f"{fmt(statistics['std'])}"
    )

    print(
        f"Median        : "
        f"{fmt(statistics['median'])}"
    )

    print(
        f"MAD           : "
        f"{fmt(statistics['mad'])}"
    )

    print(
        f"P99           : "
        f"{fmt(statistics['p99'])}"
    )


# ============================================================
# PRINT SWEEP
# ============================================================

def print_sweep_table(
    results,
):

    print()
    print(
        "SHIFT-SIGMA SWEEP"
    )
    print("-" * 92)

    print(
        f"{'SIGMA':<8}"
        f"{'DETECTED':<11}"
        f"{'INDEX':<9}"
        f"{'ACCEPT':<9}"
        f"{'MAX SHIFT':<12}"
        f"{'STABLE':<9}"
        f"{'STAGE':<8}"
        f"{'OBS':<8}"
    )

    print("-" * 92)

    for result in results:

        index = result[
            "confirmation_index"
        ]

        index_text = (
            str(index)
            if index is not None
            else "-"
        )

        print(
            f"{result['shift_sigma']:<8.2f}"
            f"{str(result['detected']):<11}"
            f"{index_text:<9}"
            f"{str(result['accepted']):<9}"
            f"{result['max_shift_strength']:<12.3f}"
            f"{result['max_stable_blocks']:<9}"
            f"{result['max_stage']:<8}"
            f"{result['observations_used']:<8}"
        )


# ============================================================
# MODEL SUMMARY
# ============================================================

def print_model_summary(
    model_name,
    calibration_scores,
    regime_scores,
    results,
):

    config = get_model_config(
        model_name
    )

    candidates = (
        summarize_candidates(
            results
        )
    )

    print()
    print("=" * 80)
    print(
        f"MODEL: {model_name.upper()}"
    )
    print("=" * 80)

    print(
        f"Stability tolerance : "
        f"{config['stability_tolerance']:.2f}"
    )

    print(
        f"Shift sweep         : "
        f"{config['shift_sigma_sweep']}"
    )

    print_statistics(
        "CALIBRATION",
        calculate_statistics(
            calibration_scores
        ),
    )

    print_statistics(
        "SEASONAL",
        calculate_statistics(
            regime_scores
        ),
    )

    print_sweep_table(
        results
    )

    print()
    print(
        "SUCCESSFUL RANGE"
    )
    print("-" * 80)

    if candidates[
        "lowest"
    ] is None:

        print(
            "No shift_sigma value produced "
            "confirmation + acceptance."
        )

        print(
            "This model requires further "
            "stability calibration."
        )

    else:

        lowest = candidates[
            "lowest"
        ]["shift_sigma"]

        highest = candidates[
            "highest"
        ]["shift_sigma"]

        recommended = candidates[
            "recommended"
        ]["shift_sigma"]

        print(
            f"Lowest successful : "
            f"{lowest:.2f}"
        )

        print(
            f"Highest successful: "
            f"{highest:.2f}"
        )

        print(
            f"Candidate midpoint: "
            f"{recommended:.2f}"
        )


# ============================================================
# FINAL SUMMARY
# ============================================================

def print_final_summary(
    all_results,
):

    print()
    print("=" * 80)
    print(
        "MODEL-SPECIFIC REGIME SUMMARY"
    )
    print("=" * 80)

    print()

    print(
        f"{'MODEL':<10}"
        f"{'TOL':<8}"
        f"{'SUCCESS':<10}"
        f"{'LOW':<8}"
        f"{'HIGH':<8}"
        f"{'CANDIDATE':<10}"
    )

    print("-" * 58)

    for model_name, results in (
        all_results.items()
    ):

        config = get_model_config(
            model_name
        )

        candidates = (
            summarize_candidates(
                results
            )
        )

        if candidates[
            "lowest"
        ] is None:

            print(
                f"{model_name:<10}"
                f"{config['stability_tolerance']:<8.2f}"
                f"{0:<10}"
                f"{'-':<8}"
                f"{'-':<8}"
                f"{'-':<10}"
            )

            continue

        lowest = candidates[
            "lowest"
        ]["shift_sigma"]

        highest = candidates[
            "highest"
        ]["shift_sigma"]

        recommended = candidates[
            "recommended"
        ]["shift_sigma"]

        success_count = len(
            successful_results(
                results
            )
        )

        print(
            f"{model_name:<10}"
            f"{config['stability_tolerance']:<8.2f}"
            f"{success_count:<10}"
            f"{lowest:<8.2f}"
            f"{highest:<8.2f}"
            f"{recommended:<10.2f}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print(
        "MODEL-SPECIFIC REGIME CALIBRATION"
    )
    print("=" * 80)

    print()
    print(
        f"Calibration : "
        f"{CALIBRATION_DATASET}"
    )

    print(
        f"Seasonal    : "
        f"{SEASONAL_DATASET}"
    )

    if not CALIBRATION_DATASET.exists():
        raise FileNotFoundError(
            "Calibration dataset not found: "
            f"{CALIBRATION_DATASET}"
        )

    if not SEASONAL_DATASET.exists():
        raise FileNotFoundError(
            "Seasonal dataset not found: "
            f"{SEASONAL_DATASET}"
        )

    calibration_df = pd.read_csv(
        CALIBRATION_DATASET
    )

    seasonal_df = pd.read_csv(
        SEASONAL_DATASET
    )

    print()
    print(
        f"Calibration samples : "
        f"{len(calibration_df)}"
    )

    print(
        f"Seasonal samples    : "
        f"{len(seasonal_df)}"
    )

    print()
    print(
        "MODEL CONFIGURATION"
    )
    print("-" * 80)

    for model_name in get_models():

        config = get_model_config(
            model_name
        )

        print(
            f"{model_name:<10}"
            f" tolerance="
            f"{config['stability_tolerance']:.2f}"
            f"  sigma="
            f"{config['shift_sigma_sweep']}"
        )

    # --------------------------------------------------------
    # Generate scores once.
    # --------------------------------------------------------

    print()
    print(
        "GENERATING MODEL SCORES"
    )
    print("-" * 80)

    models = get_models()

    model_scores = {}

    for model_name, model in (
        models.items()
    ):

        print(
            f"  {model_name.upper()}..."
        )

        calibration_scores = (
            calculate_scores(
                calibration_df,
                model,
            )
        )

        seasonal_scores = (
            calculate_scores(
                seasonal_df,
                model,
            )
        )

        model_scores[
            model_name
        ] = {
            "calibration":
                calibration_scores,
            "seasonal":
                seasonal_scores,
        }

    print(
        "Scores generated."
    )

    # --------------------------------------------------------
    # Run each model independently.
    # --------------------------------------------------------

    all_results = {}

    for model_name in models:

        scores = model_scores[
            model_name
        ]

        results = calibrate_model(
            model_name,
            scores["calibration"],
            scores["seasonal"],
        )

        all_results[
            model_name
        ] = results

        print_model_summary(
            model_name,
            scores["calibration"],
            scores["seasonal"],
            results,
        )

    # --------------------------------------------------------
    # Final compact comparison.
    # --------------------------------------------------------

    print_final_summary(
        all_results
    )

    # --------------------------------------------------------
    # Interpretation.
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print(
        "INTERPRETATION"
    )
    print("=" * 80)

    for model_name, results in (
        all_results.items()
    ):

        candidates = (
            summarize_candidates(
                results
            )
        )

        if candidates[
            "recommended"
        ] is None:

            print()
            print(
                f"[INFO] {model_name.upper()}: "
                "no successful configuration."
            )

            if (
                model_name.lower()
                == "lof"
            ):
                print(
                    "       LOF still requires "
                    "stability investigation."
                )

        else:

            recommended = candidates[
                "recommended"
            ]["shift_sigma"]

            print()
            print(
                f"[PASS] {model_name.upper()}: "
                "seasonal regime confirmed "
                "and accepted."
            )

            print(
                f"       Candidate sigma: "
                f"{recommended:.2f}"
            )

            if (
                model_name.lower()
                == "lof"
            ):

                print(
                    "       LOF was evaluated "
                    "with its model-specific "
                    "stability tolerance."
                )

    print()
    print("=" * 80)
    print(
        "IMPORTANT"
    )
    print("=" * 80)

    print(
        "Do NOT put the candidate sigma "
        "directly into production yet."
    )

    print(
        "The next test must validate each "
        "model against:"
    )

    print(
        "  1. normal data"
    )

    print(
        "  2. seasonal normal data"
    )

    print(
        "  3. true temporal drift"
    )

    print(
        "  4. temperature spikes"
    )

    print(
        "  5. fixed vs adaptive threshold "
        "performance"
    )

    print()
    print(
        "For LOF specifically, the important "
        "question is whether the wider "
        "stability tolerance allows seasonal "
        "acceptance WITHOUT accepting gradual "
        "temporal drift."
    )

    print()
    print("=" * 80)
    print(
        "MODEL-SPECIFIC REGIME CALIBRATION COMPLETED"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()