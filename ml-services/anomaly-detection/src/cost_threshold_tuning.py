import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.metrics import (
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
)


# ============================================================
# Project paths
# ============================================================

project_root = (
    Path(__file__).resolve().parent.parent
)

if str(project_root) not in sys.path:
    sys.path.insert(
        0,
        str(project_root),
    )


output_dir = (
    project_root / "output"
)

models_dir = (
    project_root / "models"
)


# ============================================================
# Business costs
# ============================================================

COST_FP = 2
COST_FN = 500


# ============================================================
# Configuration
# ============================================================

FEATURE_COLUMNS = [
    "temperature",
    "humidity",
    "stock_count",
]


DATASETS = {
    "temperature_spike":
        "test_temperature_spike.csv",

    "temperature_drift":
        "test_temperature_drift.csv",

    "stock_anomaly":
        "test_stock_anomaly.csv",

    "combined_anomaly":
        "test_combined_anomaly.csv",
}


MODEL_FILES = {
    "Isolation Forest":
        "isolation_forest_model.joblib",

    "One-Class SVM":
        "one_class_svm_model.joblib",

    "Local Outlier Factor":
        "lof_model.joblib",
}


# ============================================================
# Primary production datasets
# ============================================================
#
# Drift is deliberately excluded from production threshold
# optimization because it is a slow temporal phenomenon.
#
# It is still evaluated separately using the final production
# threshold.
# ============================================================

PRIMARY_DATASETS = [
    "temperature_spike",
    "stock_anomaly",
    "combined_anomaly",
]


# ============================================================
# Threshold grid configuration
# ============================================================

MAX_THRESHOLDS = 201


# ============================================================
# Load datasets
# ============================================================

def load_test_datasets():
    """
    Load all R4 anomaly datasets.
    """

    datasets = {}

    for dataset_name, filename in DATASETS.items():

        path = (
            output_dir / filename
        )

        if not path.exists():

            raise FileNotFoundError(
                f"Test dataset not found: {path}"
            )

        datasets[dataset_name] = (
            pd.read_csv(path)
        )

    return datasets


# ============================================================
# Load deployed models
# ============================================================

def load_deployed_models():
    """
    Load the currently deployed models.
    """

    models = {}

    for model_name, filename in (
        MODEL_FILES.items()
    ):

        path = (
            models_dir / filename
        )

        if not path.exists():

            raise FileNotFoundError(
                f"Model file not found: {path}"
            )

        models[model_name] = (
            joblib.load(path)
        )

    return models


# ============================================================
# Extract project anomaly score
# ============================================================

def get_anomaly_scores(
    model,
    features,
):
    """
    Return the project's continuous anomaly score.

    PROJECT SCORE CONVENTION
    ------------------------

    sklearn's decision_function():

        higher = more normal
        lower  = more anomalous

    Therefore this project defines:

        anomaly_score = -decision_function()

    So:

        HIGHER anomaly_score
            = MORE ANOMALOUS

        LOWER anomaly_score
            = MORE NORMAL

    Supported model structures
    --------------------------

    1. Raw sklearn estimator:

        model.decision_function(features)

    2. Project wrapper with a score() method:

        model.score(features)

        The wrapper is responsible for any required
        preprocessing/scaling.

    3. Project wrapper containing the sklearn estimator:

        model.model.decision_function(features)

    IMPORTANT
    ---------

    Wrapper score() is checked before model.model because
    wrappers such as One-Class SVM may perform scaling inside
    their score() method.
    """

    # ========================================================
    # CASE 1
    # ========================================================
    #
    # Raw sklearn estimator.
    #
    # Prefer decision_function() directly.
    #
    # This must be checked before score(), because sklearn
    # estimators also have a generic score() method that is
    # NOT the anomaly decision score.
    # ========================================================

    if hasattr(
        model,
        "decision_function",
    ):

        raw_score = (
            model
            .decision_function(
                features
            )
        )

        raw_score = np.asarray(
            raw_score,
            dtype=float,
        )

        if raw_score.ndim != 1:

            raw_score = (
                raw_score.reshape(-1)
            )

        if not np.all(
            np.isfinite(raw_score)
        ):

            raise ValueError(
                "Model decision_function() "
                "produced non-finite values."
            )

        # ----------------------------------------------------
        # Convert normality score to anomaly score.
        # ----------------------------------------------------

        return -raw_score

    # ========================================================
    # CASE 2
    # ========================================================
    #
    # Project wrapper exposing score().
    #
    # For this project, wrapper score() returns the underlying
    # decision_function() score.
    #
    # Therefore invert it.
    # ========================================================

    if hasattr(
        model,
        "score",
    ):

        raw_score = (
            model.score(
                features
            )
        )

        raw_score = np.asarray(
            raw_score,
            dtype=float,
        )

        if raw_score.ndim != 1:

            raw_score = (
                raw_score.reshape(-1)
            )

        if not np.all(
            np.isfinite(raw_score)
        ):

            raise ValueError(
                "Model score() "
                "produced non-finite values."
            )

        # ----------------------------------------------------
        # Project anomaly score.
        # ----------------------------------------------------

        return -raw_score

    # ========================================================
    # CASE 3
    # ========================================================
    #
    # Project wrapper without score(), but containing the
    # fitted sklearn estimator as .model.
    #
    # This is required for the IsolationForestModel wrapper.
    # ========================================================

    if hasattr(
        model,
        "model",
    ):

        underlying_model = (
            model.model
        )

        if hasattr(
            underlying_model,
            "decision_function",
        ):

            raw_score = (
                underlying_model
                .decision_function(
                    features
                )
            )

            raw_score = np.asarray(
                raw_score,
                dtype=float,
            )

            if raw_score.ndim != 1:

                raw_score = (
                    raw_score.reshape(-1)
                )

            if not np.all(
                np.isfinite(raw_score)
            ):

                raise ValueError(
                    "Underlying sklearn "
                    "model produced non-finite "
                    "decision_function scores."
                )

            # ------------------------------------------------
            # Convert normality score to anomaly score.
            # ------------------------------------------------

            return -raw_score

    # ========================================================
    # No continuous scoring interface available.
    # ========================================================

    raise AttributeError(
        f"{type(model).__name__} does not expose "
        "a usable continuous anomaly score. "
        "Expected one of: "
        "decision_function(), "
        "score(), or "
        "model.decision_function()."
    )


# ============================================================
# Reference predictions
# ============================================================

def get_reference_predictions(
    model,
    features,
):
    """
    Obtain the model's native anomaly predictions.

        -1 = anomaly
        +1 = normal
    """

    predictions = model.predict(
        features
    )

    predictions = np.asarray(
        predictions
    )

    return (
        predictions == -1
    ).astype(int)


# ============================================================
# Check score convention
# ============================================================

def calculate_reference_threshold(
    scores,
    reference_predictions,
):
    """
    Find the threshold on the PROJECT ANOMALY SCORE that most
    closely reproduces the model's native predict() output.

    Project score convention:

        higher score = more anomalous

    Therefore:

        score >= threshold
            -> anomaly

    This function is only a diagnostic/reference check.
    It does NOT choose the production threshold.
    """

    unique_scores = np.unique(
        scores
    )

    if len(unique_scores) < 2:

        raise ValueError(
            "Continuous anomaly scores contain "
            "fewer than two unique values."
        )

    thresholds = (
        unique_scores[:-1]
        + unique_scores[1:]
    ) / 2.0

    lower_margin = max(
        1.0,
        abs(
            unique_scores[0]
        ) * 0.01,
    )

    upper_margin = max(
        1.0,
        abs(
            unique_scores[-1]
        ) * 0.01,
    )

    thresholds = np.concatenate(
        [
            [
                unique_scores[0]
                - lower_margin
            ],
            thresholds,
            [
                unique_scores[-1]
                + upper_margin
            ],
        ]
    )

    best_threshold = None
    best_agreement = -1.0

    for threshold in thresholds:

        predicted = (
            scores >= threshold
        ).astype(int)

        agreement = float(
            np.mean(
                predicted
                == reference_predictions
            )
        )

        if agreement > best_agreement:

            best_agreement = (
                agreement
            )

            best_threshold = (
                float(threshold)
            )

    return (
        best_threshold,
        best_agreement,
    )


# ============================================================
# Build common threshold grid
# ============================================================

def build_thresholds(
    scores,
    max_thresholds=MAX_THRESHOLDS,
):
    """
    Build ONE common threshold grid for a model.

    The grid is built from the PROJECT ANOMALY SCORE:

        higher = more anomalous

    The same threshold grid is then applied to:

        temperature_spike
        stock_anomaly
        combined_anomaly
        temperature_drift
    """

    scores = np.asarray(
        scores,
        dtype=float,
    )

    unique_scores = np.unique(
        scores
    )

    if len(unique_scores) < 2:

        raise ValueError(
            "Cannot build threshold grid "
            "from fewer than two unique scores."
        )

    # --------------------------------------------------------
    # Few unique scores:
    # use all separating thresholds.
    # --------------------------------------------------------

    if len(unique_scores) <= (
        max_thresholds - 2
    ):

        thresholds = (
            unique_scores[:-1]
            + unique_scores[1:]
        ) / 2.0

        lower_margin = max(
            1.0,
            abs(
                unique_scores[0]
            ) * 0.01,
        )

        upper_margin = max(
            1.0,
            abs(
                unique_scores[-1]
            ) * 0.01,
        )

        thresholds = np.concatenate(
            [
                [
                    unique_scores[0]
                    - lower_margin
                ],
                thresholds,
                [
                    unique_scores[-1]
                    + upper_margin
                ],
            ]
        )

        return np.unique(
            thresholds
        )

    # --------------------------------------------------------
    # Large score sets:
    # use quantiles.
    # --------------------------------------------------------

    quantiles = np.linspace(
        0.0,
        1.0,
        max_thresholds,
    )

    thresholds = np.quantile(
        scores,
        quantiles,
    )

    thresholds = np.unique(
        thresholds
    )

    # Add outside boundaries.

    lower_margin = max(
        1.0,
        abs(
            unique_scores[0]
        ) * 0.01,
    )

    upper_margin = max(
        1.0,
        abs(
            unique_scores[-1]
        ) * 0.01,
    )

    thresholds = np.concatenate(
        [
            [
                unique_scores[0]
                - lower_margin
            ],
            thresholds,
            [
                unique_scores[-1]
                + upper_margin
            ],
        ]
    )

    return np.unique(
        thresholds
    )


# ============================================================
# Evaluate one threshold
# ============================================================

def evaluate_threshold(
    scores,
    y_true,
    threshold,
):
    """
    Evaluate one threshold using the project's anomaly score.

    IMPORTANT:

        score >= threshold
            -> anomaly

        score < threshold
            -> normal
    """

    y_pred = (
        scores >= threshold
    ).astype(int)

    tn, fp, fn, tp = (
        confusion_matrix(
            y_true,
            y_pred,
            labels=[0, 1],
        ).ravel()
    )

    precision = precision_score(
        y_true,
        y_pred,
        zero_division=0,
    )

    recall = recall_score(
        y_true,
        y_pred,
        zero_division=0,
    )

    f1 = f1_score(
        y_true,
        y_pred,
        zero_division=0,
    )

    expected_cost = (
        fp * COST_FP
        +
        fn * COST_FN
    )

    return {
        "Threshold":
            float(threshold),

        "Precision":
            float(precision),

        "Recall":
            float(recall),

        "F1":
            float(f1),

        "TP":
            int(tp),

        "TN":
            int(tn),

        "FP":
            int(fp),

        "FN":
            int(fn),

        "Expected Cost":
            float(expected_cost),
    }


# ============================================================
# Prepare one model
# ============================================================

def prepare_model_scores(
    model,
    datasets,
):
    """
    Calculate project anomaly scores for every dataset.

    Returns
    -------
    tuple
        (
            prepared,
            native_threshold,
            agreement,
            combined_primary_scores,
        )

    IMPORTANT:

        score = -decision_function()

        higher score = more anomalous
    """

    prepared = {}

    all_primary_scores = []

    all_primary_predictions = []

    # --------------------------------------------------------
    # Calculate scores for every dataset.
    # --------------------------------------------------------

    for dataset_name, dataset in (
        datasets.items()
    ):

        features = dataset[
            FEATURE_COLUMNS
        ].to_numpy()

        y_true = (
            dataset[
                "is_anomaly"
            ]
            .to_numpy(
                dtype=int
            )
        )

        # ----------------------------------------------------
        # PROJECT ANOMALY SCORE
        # ----------------------------------------------------

        scores = get_anomaly_scores(
            model,
            features,
        )

        native_predictions = (
            get_reference_predictions(
                model,
                features,
            )
        )

        prepared[dataset_name] = {
            "scores":
                scores,

            "y_true":
                y_true,

            "native_predictions":
                native_predictions,
        }

        if dataset_name in (
            PRIMARY_DATASETS
        ):

            all_primary_scores.append(
                scores
            )

            all_primary_predictions.append(
                native_predictions
            )

    # --------------------------------------------------------
    # Combine primary scores.
    # --------------------------------------------------------

    combined_scores = np.concatenate(
        all_primary_scores
    )

    combined_predictions = np.concatenate(
        all_primary_predictions
    )

    # --------------------------------------------------------
    # Diagnostic native threshold.
    #
    # This should approximately reproduce model.predict().
    # --------------------------------------------------------

    (
        native_threshold,
        agreement,
    ) = calculate_reference_threshold(
        combined_scores,
        combined_predictions,
    )

    return (
        prepared,
        native_threshold,
        agreement,
        combined_scores,
    )


# ============================================================
# Create complete threshold sweep
# ============================================================

def create_model_threshold_results(
    model,
    model_name,
    datasets,
):
    """
    Create threshold results for ONE model.

    A SINGLE common threshold grid is used across:

        temperature_spike
        stock_anomaly
        combined_anomaly

    and the same grid is reported for drift.

    Score convention:

        higher_is_anomaly
    """

    (
        prepared,
        native_threshold,
        agreement,
        combined_primary_scores,
    ) = prepare_model_scores(
        model,
        datasets,
    )

    thresholds = build_thresholds(
        combined_primary_scores
    )

    rows = []

    # --------------------------------------------------------
    # Evaluate every dataset using the SAME thresholds.
    # --------------------------------------------------------

    for dataset_name in (
        datasets.keys()
    ):

        scores = prepared[
            dataset_name
        ]["scores"]

        y_true = prepared[
            dataset_name
        ]["y_true"]

        for threshold in thresholds:

            row = evaluate_threshold(
                scores=scores,
                y_true=y_true,
                threshold=threshold,
            )

            row.update(
                {
                    "Model":
                        model_name,

                    "Test Dataset":
                        dataset_name,

                    "Score Direction":
                        "higher_is_anomaly",

                    "Native Threshold":
                        native_threshold,

                    "Direction Agreement":
                        agreement,
                }
            )

            rows.append(
                row
            )

    return pd.DataFrame(
        rows
    )


# ============================================================
# Aggregate primary datasets
# ============================================================

def aggregate_primary_cost(
    model_results,
):
    """
    Aggregate the SAME threshold across:

        temperature_spike
        stock_anomaly
        combined_anomaly

    This is the production calculation.
    """

    primary = (
        model_results[
            model_results[
                "Test Dataset"
            ].isin(
                PRIMARY_DATASETS
            )
        ]
        .copy()
    )

    if primary.empty:

        return pd.DataFrame()

    grouped = (
        primary
        .groupby(
            [
                "Model",
                "Score Direction",
                "Native Threshold",
                "Direction Agreement",
                "Threshold",
            ],
            dropna=False,
        )
        .agg(
            {
                "TP": "sum",
                "TN": "sum",
                "FP": "sum",
                "FN": "sum",
            }
        )
        .reset_index()
    )

    # --------------------------------------------------------
    # Aggregate precision.
    # --------------------------------------------------------

    denominator = (
        grouped["TP"]
        + grouped["FP"]
    )

    grouped[
        "Precision"
    ] = np.where(
        denominator > 0,
        grouped["TP"]
        / denominator,
        0.0,
    )

    # --------------------------------------------------------
    # Aggregate recall.
    # --------------------------------------------------------

    denominator = (
        grouped["TP"]
        + grouped["FN"]
    )

    grouped[
        "Recall"
    ] = np.where(
        denominator > 0,
        grouped["TP"]
        / denominator,
        0.0,
    )

    # --------------------------------------------------------
    # Aggregate F1.
    # --------------------------------------------------------

    denominator = (
        grouped["Precision"]
        + grouped["Recall"]
    )

    grouped[
        "F1"
    ] = np.where(
        denominator > 0,
        (
            2
            * grouped["Precision"]
            * grouped["Recall"]
            / denominator
        ),
        0.0,
    )

    # --------------------------------------------------------
    # Business cost.
    # --------------------------------------------------------

    grouped[
        "Expected Cost"
    ] = (
        grouped["FP"] * COST_FP
        +
        grouped["FN"] * COST_FN
    )

    # --------------------------------------------------------
    # Number of primary datasets.
    # --------------------------------------------------------

    grouped[
        "Datasets Included"
    ] = len(
        PRIMARY_DATASETS
    )

    return grouped


# ============================================================
# Select production threshold
# ============================================================

def select_cost_optimal_threshold(
    primary_results,
):
    """
    Select one production threshold.

    Production objective:

        1. Minimum total Expected Cost
        2. Highest aggregate Recall
        3. Highest aggregate Precision
        4. Highest F1
        5. Lowest FP
        6. Lowest FN

    Business costs:

        FP = 2
        FN = 500

    Therefore Expected Cost is the PRIMARY selection
    criterion. Recall, Precision, and F1 are only
    tie-breakers.

    This is the ONLY threshold selector used for
    production deployment.
    """

    if primary_results.empty:

        raise RuntimeError(
            "No primary threshold results "
            "available."
        )

    selected = (
        primary_results
        .sort_values(
            by=[
                "Expected Cost",
                "Recall",
                "Precision",
                "F1",
                "FP",
                "FN",
            ],
            ascending=[
                True,
                False,
                False,
                False,
                True,
                True,
            ],
            kind="mergesort",
        )
        .iloc[0]
        .copy()
    )

    return selected


# ============================================================
# Select F1 diagnostic threshold
# ============================================================

def select_f1_diagnostic_threshold(
    primary_results,
):
    """
    Select one F1 diagnostic threshold.

    This is NOT a production selector.

    It exists only to provide a diagnostic comparison between:

        F1-oriented selection
            versus
        business-cost selection.

    The returned threshold is never used as the
    production threshold.
    """

    if primary_results.empty:

        raise RuntimeError(
            "No primary threshold results "
            "available for F1 diagnostic analysis."
        )

    selected = (
        primary_results
        .sort_values(
            by=[
                "F1",
                "Recall",
                "Precision",
                "Expected Cost",
            ],
            ascending=[
                False,
                False,
                False,
                True,
            ],
            kind="mergesort",
        )
        .iloc[0]
        .copy()
    )

    return selected


# ============================================================
# Main
# ============================================================

def run_cost_threshold_tuning():
    """
    Run the complete R4.5 cost-based threshold analysis.

    Production threshold selection is based on:

        Expected Cost
            ↓
        Recall
            ↓
        Precision
            ↓
        F1

    F1 threshold selection is reported only as a
    diagnostic comparison.
    """

    print(
        "=" * 70
    )

    print(
        "R4.5 COST-BASED THRESHOLD TUNING"
    )

    print(
        "=" * 70
    )

    print()

    print(
        f"False-positive cost : {COST_FP}"
    )

    print(
        f"False-negative cost : {COST_FN}"
    )

    print()

    print(
        "Primary production objective:"
    )

    print(
        "  Minimize expected business cost."
    )

    print()

    print(
        "Production selection priority:"
    )

    print(
        "  1. Lowest Expected Cost"
    )

    print(
        "  2. Highest Recall"
    )

    print(
        "  3. Highest Precision"
    )

    print(
        "  4. Highest F1"
    )

    print()

    print(
        "F1 threshold:"
    )

    print(
        "  Diagnostic comparison only."
    )

    print(
        "  NOT used for production selection."
    )

    print()

    print(
        "Project anomaly-score convention:"
    )

    print(
        "  score = -model.decision_function(features)"
    )

    print(
        "  higher score = MORE ANOMALOUS"
    )

    print(
        "  score >= threshold -> ANOMALY"
    )

    print()

    print(
        "Primary cost datasets:"
    )

    for dataset_name in (
        PRIMARY_DATASETS
    ):

        print(
            f"  - {dataset_name}"
        )

    print()

    print(
        "Temperature drift is reported separately "
        "and does not dominate threshold selection."
    )

    print()

    # --------------------------------------------------------
    # Load datasets and models.
    # --------------------------------------------------------

    datasets = (
        load_test_datasets()
    )

    models = (
        load_deployed_models()
    )

    all_results = []

    production_rows = []

    drift_rows = []

    # --------------------------------------------------------
    # Process every model.
    # --------------------------------------------------------

    for model_name, model in (
        models.items()
    ):

        print()
        print(
            model_name
        )

        print(
            "-" * 70
        )

        print(
            "  Building common PROJECT anomaly-score grid..."
        )

        model_results = (
            create_model_threshold_results(
                model=model,
                model_name=model_name,
                datasets=datasets,
            )
        )

        all_results.append(
            model_results
        )

        # ----------------------------------------------------
        # Primary aggregate.
        # ----------------------------------------------------

        primary_results = (
            aggregate_primary_cost(
                model_results
            )
        )

        if primary_results.empty:

            raise RuntimeError(
                f"No primary results for "
                f"{model_name}."
            )

        cost_best = (
            select_cost_optimal_threshold(
                primary_results
            )
        )

        f1_diagnostic = (
            select_f1_diagnostic_threshold(
                primary_results
            )
        )

        # ----------------------------------------------------
        # Print score direction.
        # ----------------------------------------------------

        print()

        print(
            "  Score direction:"
            " higher_is_anomaly"
        )

        print(
            "  Native predict() agreement:"
            f" {cost_best['Direction Agreement']:.4f}"
        )

        print()

        # ----------------------------------------------------
        # F1 diagnostic result.
        # ----------------------------------------------------

        print(
            "  F1 diagnostic threshold:"
            f" {f1_diagnostic['Threshold']:.8f}"
        )

        print(
            "    Precision:"
            f" {f1_diagnostic['Precision']:.4f}"
        )

        print(
            "    Recall:"
            f" {f1_diagnostic['Recall']:.4f}"
        )

        print(
            "    F1:"
            f" {f1_diagnostic['F1']:.4f}"
        )

        print(
            "    FP:"
            f" {int(f1_diagnostic['FP'])}"
        )

        print(
            "    FN:"
            f" {int(f1_diagnostic['FN'])}"
        )

        print(
            "    Expected Cost:"
            f" {f1_diagnostic['Expected Cost']:.0f}"
        )

        print()

        # ----------------------------------------------------
        # Cost result.
        # ----------------------------------------------------

        print(
            "  COST-optimal production threshold:"
            f" {cost_best['Threshold']:.8f}"
        )

        print(
            "    Precision:"
            f" {cost_best['Precision']:.4f}"
        )

        print(
            "    Recall:"
            f" {cost_best['Recall']:.4f}"
        )

        print(
            "    F1:"
            f" {cost_best['F1']:.4f}"
        )

        print(
            "    FP:"
            f" {int(cost_best['FP'])}"
        )

        print(
            "    FN:"
            f" {int(cost_best['FN'])}"
        )

        print(
            "    Expected Cost:"
            f" {cost_best['Expected Cost']:.0f}"
        )

        # ----------------------------------------------------
        # Cost reduction.
        # ----------------------------------------------------

        cost_reduction = (
            f1_diagnostic["Expected Cost"]
            -
            cost_best["Expected Cost"]
        )

        if (
            f1_diagnostic["Expected Cost"]
            > 0
        ):

            cost_reduction_percent = (
                cost_reduction
                /
                f1_diagnostic["Expected Cost"]
                * 100.0
            )

        else:

            cost_reduction_percent = 0.0

        print()

        print(
            "  Cost reduction vs F1 diagnostic:"
            f" {cost_reduction:.0f}"
            f" ({cost_reduction_percent:.2f}%)"
        )

        # ----------------------------------------------------
        # Production decision row.
        # ----------------------------------------------------

        production_rows.append(
            {
                "Model":
                    model_name,

                "Score Direction":
                    "higher_is_anomaly",

                "Native Threshold":
                    cost_best[
                        "Native Threshold"
                    ],

                "Direction Agreement":
                    cost_best[
                        "Direction Agreement"
                    ],

                "F1 Diagnostic Threshold":
                    f1_diagnostic[
                        "Threshold"
                    ],

                "F1 Diagnostic Precision":
                    f1_diagnostic[
                        "Precision"
                    ],

                "F1 Diagnostic Recall":
                    f1_diagnostic[
                        "Recall"
                    ],

                "F1 Diagnostic Score":
                    f1_diagnostic[
                        "F1"
                    ],

                "F1 Diagnostic TP":
                    f1_diagnostic[
                        "TP"
                    ],

                "F1 Diagnostic FP":
                    f1_diagnostic[
                        "FP"
                    ],

                "F1 Diagnostic FN":
                    f1_diagnostic[
                        "FN"
                    ],

                "F1 Diagnostic Expected Cost":
                    f1_diagnostic[
                        "Expected Cost"
                    ],

                "Cost Threshold":
                    cost_best[
                        "Threshold"
                    ],

                "Cost Precision":
                    cost_best[
                        "Precision"
                    ],

                "Cost Recall":
                    cost_best[
                        "Recall"
                    ],

                "Cost F1":
                    cost_best[
                        "F1"
                    ],

                "Cost TP":
                    cost_best[
                        "TP"
                    ],

                "Cost FP":
                    cost_best[
                        "FP"
                    ],

                "Cost FN":
                    cost_best[
                        "FN"
                    ],

                "Cost Expected Cost":
                    cost_best[
                        "Expected Cost"
                    ],

                "Cost Reduction":
                    cost_reduction,

                "Cost Reduction %":
                    cost_reduction_percent,

                "Primary Datasets":
                    ",".join(
                        PRIMARY_DATASETS
                    ),
            }
        )

        # ----------------------------------------------------
        # Drift report.
        # ----------------------------------------------------

        drift = (
            model_results[
                model_results[
                    "Test Dataset"
                ]
                == "temperature_drift"
            ]
            .copy()
        )

        if not drift.empty:

            drift_best = (
                drift
                .sort_values(
                    by=[
                        "F1",
                        "Recall",
                        "Precision",
                        "Expected Cost",
                    ],
                    ascending=[
                        False,
                        False,
                        False,
                        True,
                    ],
                    kind="mergesort",
                )
                .iloc[0]
            )

            # ------------------------------------------------
            # Evaluate production threshold on drift.
            #
            # Informational only.
            # ------------------------------------------------

            production_threshold = (
                cost_best[
                    "Threshold"
                ]
            )

            production_drift = (
                drift[
                    np.isclose(
                        drift[
                            "Threshold"
                        ].to_numpy(
                            dtype=float
                        ),
                        float(
                            production_threshold
                        ),
                        rtol=1e-12,
                        atol=1e-12,
                    )
                ]
            )

            if production_drift.empty:

                production_drift_row = {
                    "Precision":
                        np.nan,

                    "Recall":
                        np.nan,

                    "F1":
                        np.nan,

                    "TP":
                        np.nan,

                    "FP":
                        np.nan,

                    "FN":
                        np.nan,

                    "Expected Cost":
                        np.nan,
                }

            else:

                production_drift_row = (
                    production_drift.iloc[0]
                )

            drift_rows.append(
                {
                    "Model":
                        model_name,

                    "Score Direction":
                        "higher_is_anomaly",

                    "F1 Diagnostic Threshold":
                        drift_best[
                            "Threshold"
                        ],

                    "F1 Diagnostic Precision":
                        drift_best[
                            "Precision"
                        ],

                    "F1 Diagnostic Recall":
                        drift_best[
                            "Recall"
                        ],

                    "F1 Diagnostic Score":
                        drift_best[
                            "F1"
                        ],

                    "F1 Diagnostic TP":
                        drift_best[
                            "TP"
                        ],

                    "F1 Diagnostic FP":
                        drift_best[
                            "FP"
                        ],

                    "F1 Diagnostic FN":
                        drift_best[
                            "FN"
                        ],

                    "F1 Diagnostic Expected Cost":
                        drift_best[
                            "Expected Cost"
                        ],

                    "Production Threshold":
                        production_threshold,

                    "Production Precision":
                        production_drift_row[
                            "Precision"
                        ],

                    "Production Recall":
                        production_drift_row[
                            "Recall"
                        ],

                    "Production F1":
                        production_drift_row[
                            "F1"
                        ],

                    "Production TP":
                        production_drift_row[
                            "TP"
                        ],

                    "Production FP":
                        production_drift_row[
                            "FP"
                        ],

                    "Production FN":
                        production_drift_row[
                            "FN"
                        ],

                    "Production Expected Cost":
                        production_drift_row[
                            "Expected Cost"
                        ],
                }
            )

    # ========================================================
    # Combine all threshold results.
    # ========================================================

    all_results_df = (
        pd.concat(
            all_results,
            ignore_index=True,
        )
    )

    complete_file = (
        output_dir
        / "cost_threshold_tuning_results.csv"
    )

    all_results_df.to_csv(
        complete_file,
        index=False,
    )

    # ========================================================
    # Build primary aggregate file.
    # ========================================================

    primary_all = []

    for model_name in (
        all_results_df[
            "Model"
        ].unique()
    ):

        model_df = (
            all_results_df[
                all_results_df[
                    "Model"
                ]
                == model_name
            ]
        )

        primary_df = (
            aggregate_primary_cost(
                model_df
            )
        )

        primary_all.append(
            primary_df
        )

    primary_results_df = (
        pd.concat(
            primary_all,
            ignore_index=True,
        )
    )

    primary_file = (
        output_dir
        / "cost_threshold_primary_results.csv"
    )

    primary_results_df.to_csv(
        primary_file,
        index=False,
    )

    # ========================================================
    # Production decision file.
    # ========================================================

    winners_df = pd.DataFrame(
        production_rows
    )

    winners_file = (
        output_dir
        / "cost_threshold_production_decision.csv"
    )

    winners_df.to_csv(
        winners_file,
        index=False,
    )

    # ========================================================
    # Drift report.
    # ========================================================

    drift_df = pd.DataFrame(
        drift_rows
    )

    drift_file = (
        output_dir
        / "cost_threshold_drift_report.csv"
    )

    drift_df.to_csv(
        drift_file,
        index=False,
    )

    # ========================================================
    # Final summary.
    # ========================================================

    print()

    print(
        "=" * 70
    )

    print(
        "PRIMARY PRODUCTION DECISION"
    )

    print(
        "=" * 70
    )

    for _, row in (
        winners_df.iterrows()
    ):

        print()

        print(
            row["Model"]
        )

        print(
            "-" * 70
        )

        print(
            "Score direction:"
            " higher_is_anomaly"
        )

        print(
            "Production threshold:"
            f" {row['Cost Threshold']:.8f}"
        )

        print(
            "Aggregate precision:"
            f" {row['Cost Precision']:.4f}"
        )

        print(
            "Aggregate recall:"
            f" {row['Cost Recall']:.4f}"
        )

        print(
            "Aggregate F1:"
            f" {row['Cost F1']:.4f}"
        )

        print(
            "Total TP:"
            f" {int(row['Cost TP'])}"
        )

        print(
            "Total FP:"
            f" {int(row['Cost FP'])}"
        )

        print(
            "Total FN:"
            f" {int(row['Cost FN'])}"
        )

        print(
            "Expected business cost:"
            f" {row['Cost Expected Cost']:.0f}"
        )

        print(
            "Cost reduction vs F1 diagnostic:"
            f" {row['Cost Reduction']:.0f}"
            f" ({row['Cost Reduction %']:.2f}%)"
        )

    print()

    print(
        "=" * 70
    )

    print(
        "R4.5 COST TUNING COMPLETED"
    )

    print(
        "=" * 70
    )

    print()

    print(
        "Complete sweep:"
    )

    print(
        f"  {complete_file}"
    )

    print()

    print(
        "Primary aggregate:"
    )

    print(
        f"  {primary_file}"
    )

    print()

    print(
        "Production decision:"
    )

    print(
        f"  {winners_file}"
    )

    print()

    print(
        "Drift report:"
    )

    print(
        f"  {drift_file}"
    )

    print()

    print(
        "Production selection rule:"
    )

    print(
        "  1. Minimize TOTAL expected business cost "
        "across spike + stock + combined."
    )

    print(
        "  2. If tied, maximize aggregate recall."
    )

    print(
        "  3. If still tied, maximize aggregate precision."
    )

    print(
        "  4. If still tied, maximize F1."
    )

    print()

    print(
        "F1 diagnostic:"
    )

    print(
        "  Used only for comparison."
    )

    print(
        "  It is NOT used to select the production threshold."
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "  Production anomaly rule:"
    )

    print(
        "    score = -model.decision_function(features)"
    )

    print(
        "    score >= production_threshold -> ANOMALY"
    )

    print(
        "    higher score = more anomalous"
    )

    print()

    return {
        "all_results":
            all_results_df,

        "primary_results":
            primary_results_df,

        "production_decision":
            winners_df,

        "drift_report":
            drift_df,
    }


# ============================================================
# Script entry point
# ============================================================

if __name__ == "__main__":

    run_cost_threshold_tuning()