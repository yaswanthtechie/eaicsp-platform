import numpy as np
import pandas as pd

from sklearn.metrics import (
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
)


# ==========================================================
# Production model-selection configuration
# ==========================================================

# Temperature drift is intentionally excluded from the
# point-anomaly model selection.
#
# Drift is handled separately by TemporalDetector because
# slow drift can legitimately produce delayed FN values for
# point anomaly models.

SELECTION_DATASETS = (
    "temperature_spike",
    "stock_anomaly",
    "combined_anomaly",
)

# A configuration is considered recall-eligible when its
# average recall is within this amount of the absolute
# maximum average recall.
#
# Example:
#
# Maximum recall = 1.00
# tolerance      = 0.02
#
# Minimum eligible recall = 0.98
#
# Therefore:
#
# 1.00 / 0.30 precision -> eligible
# 1.00 / 0.55 precision -> eligible
# 0.98 / 0.90 precision -> eligible
#
# The 0.98 configuration can then win because it has much
# better precision.
#
RECALL_TOLERANCE = 0.02


# ==========================================================
# Evaluation
# ==========================================================

def evaluate_model(
    model_name,
    model,
    test_datasets,
    feature_columns,
    hyperparameters,
    scaler=None,
):
    """
    Evaluate a trained model on all test datasets.

    Parameters
    ----------
    model_name : str
        Display name of the model.

    model : sklearn estimator
        Trained estimator.

    test_datasets : dict
        Dictionary containing test DataFrames.

    feature_columns : list
        Feature column names.

    hyperparameters : dict
        Hyperparameters used for this model.

    scaler : sklearn scaler, optional
        Used only for One-Class SVM.

    Returns
    -------
    list
        List of result dictionaries.
    """

    results = []

    for dataset_name, dataset in test_datasets.items():

        X_test = dataset[
            feature_columns
        ].to_numpy()

        y_true = dataset[
            "is_anomaly"
        ].to_numpy()

        if scaler is not None:

            X_test = scaler.transform(
                X_test
            )

        predictions = (
            model.predict(X_test) == -1
        ).astype(int)

        # --------------------------------------------------
        # Confusion matrix
        # --------------------------------------------------

        matrix = confusion_matrix(
            y_true,
            predictions,
            labels=[0, 1],
        )

        tn, fp, fn, tp = (
            matrix.ravel()
        )

        # --------------------------------------------------
        # Metrics
        # --------------------------------------------------

        precision = precision_score(
            y_true,
            predictions,
            zero_division=0,
        )

        recall = recall_score(
            y_true,
            predictions,
            zero_division=0,
        )

        f1 = f1_score(
            y_true,
            predictions,
            zero_division=0,
        )

        row = {
            "Model": model_name,
            "Test Dataset": dataset_name,
            "Precision": precision,
            "Recall": recall,
            "PR Score": (
                precision + recall
            ) / 2,
            "F1": f1,
            "TP": tp,
            "TN": tn,
            "FP": fp,
            "FN": fn,
        }

        row.update(
            hyperparameters
        )

        results.append(
            row
        )

    return results


# ==========================================================
# Ranking
# ==========================================================

def rank_results(
    results,
    top_n=10,
    recall_tolerance=RECALL_TOLERANCE,
):
    """
    Rank hyperparameter configurations.

    ==========================================================
    OVERALL / PRODUCTION SELECTION
    ==========================================================

    Temperature drift is NOT used to select the point
    anomaly model.

    Selection datasets:

        - temperature_spike
        - stock_anomaly
        - combined_anomaly

    Temperature drift is evaluated separately by the
    TemporalDetector.

    The production selection rule is:

        1. Find the ABSOLUTE maximum average recall across
           the three point-anomaly datasets.

        2. Keep every configuration whose average recall is
           within `recall_tolerance` of that maximum.

        3. Among those recall-eligible configurations,
           maximize average precision.

        4. If precision is tied:
              maximize minimum recall.

        5. If still tied:
              maximize average F1.

        6. If still tied:
              minimize total FP.

        7. If still tied:
              minimize total FN.

    Example:

        A:
            Recall    = 1.00
            Precision = 0.30

        B:
            Recall    = 1.00
            Precision = 0.55

        C:
            Recall    = 0.98
            Precision = 0.90

        With recall tolerance = 0.02:

            Maximum recall = 1.00
            Minimum eligible recall = 0.98

        Therefore A, B and C are all eligible.

        C wins because:

            Precision(C) = 0.90

        is higher than:

            Precision(B) = 0.55
            Precision(A) = 0.30

    IMPORTANT
    ---------

    ALL configurations remain in the returned result.

    We do NOT discard configurations merely because they
    are not recall-eligible.

    The `Recall Eligible` column identifies configurations
    inside the production selection band.

    `Rank` for OVERALL rows represents the ordering of all
    configurations, with eligible configurations ranked
    before non-eligible configurations according to the
    production rule.

    ==========================================================
    PER-DATASET RANKING
    ==========================================================

    Each individual anomaly dataset is ranked using:

        1. Recall DESC
        2. Precision DESC
        3. F1 DESC
        4. FP ASC
        5. FN ASC

    No Pareto filtering is used.

    No PR-score optimization is used.

    No F1-only selection is used.

    ==========================================================
    """

    results = pd.DataFrame(
        results
    )

    if results.empty:
        return results

    # ------------------------------------------------------
    # Validate recall tolerance
    # ------------------------------------------------------

    recall_tolerance = float(
        recall_tolerance
    )

    if not (
        0.0
        <= recall_tolerance
        <= 1.0
    ):
        raise ValueError(
            "recall_tolerance must be between 0.0 and 1.0."
        )

    # ------------------------------------------------------
    # Identify configuration columns
    # ------------------------------------------------------

    metric_columns = {
        "Test Dataset",
        "Precision",
        "Recall",
        "PR Score",
        "F1",
        "TP",
        "TN",
        "FP",
        "FN",
        "Rank",
        "Minimum Recall",
        "Recall Eligible",
        "Maximum Recall",
        "Minimum Eligible Recall",
    }

    configuration_columns = [
        column
        for column in results.columns
        if column not in metric_columns
    ]

    # ------------------------------------------------------
    # Select only the datasets used for point-anomaly
    # model selection.
    # ------------------------------------------------------

    selection_results = results[
        results["Test Dataset"].isin(
            SELECTION_DATASETS
        )
    ].copy()

    # ------------------------------------------------------
    # Make sure all required datasets are present.
    # ------------------------------------------------------

    available_selection_datasets = set(
        selection_results[
            "Test Dataset"
        ].unique()
    )

    missing_datasets = [
        dataset
        for dataset in SELECTION_DATASETS
        if dataset not in available_selection_datasets
    ]

    if missing_datasets:
        raise ValueError(
            "Required selection datasets are missing: "
            + ", ".join(
                missing_datasets
            )
        )

    # ------------------------------------------------------
    # Overall aggregation
    # ------------------------------------------------------
    #
    # Every exact hyperparameter configuration is grouped
    # across the THREE point-anomaly datasets.
    #
    # Temperature drift is deliberately excluded.
    # ------------------------------------------------------

    overall = (
        selection_results
        .groupby(
            configuration_columns,
            dropna=False,
        )
        .agg(
            {
                "Precision": "mean",
                "Recall": [
                    "mean",
                    "min",
                ],
                "PR Score": "mean",
                "F1": "mean",
                "TP": "sum",
                "TN": "sum",
                "FP": "sum",
                "FN": "sum",
            }
        )
        .reset_index()
    )

    # ------------------------------------------------------
    # Flatten MultiIndex columns
    # ------------------------------------------------------

    overall.columns = [
        " ".join(
            column
        ).strip()
        if isinstance(
            column,
            tuple,
        )
        else column
        for column in overall.columns
    ]

    # ------------------------------------------------------
    # Rename aggregated columns
    # ------------------------------------------------------

    overall.rename(
        columns={
            "Precision mean": "Precision",
            "Recall mean": "Recall",
            "Recall min": "Minimum Recall",
            "PR Score mean": "PR Score",
            "F1 mean": "F1",
            "TP sum": "TP",
            "TN sum": "TN",
            "FP sum": "FP",
            "FN sum": "FN",
        },
        inplace=True,
    )

    # ------------------------------------------------------
    # Absolute maximum recall
    # ------------------------------------------------------

    maximum_recall = float(
        overall[
            "Recall"
        ].max()
    )

    # ------------------------------------------------------
    # Minimum recall required to remain in the selection
    # band.
    # ------------------------------------------------------

    minimum_eligible_recall = max(
        0.0,
        maximum_recall
        - recall_tolerance,
    )

    # ------------------------------------------------------
    # Mark recall-eligible configurations.
    # ------------------------------------------------------

    overall[
        "Recall Eligible"
    ] = (
        overall[
            "Recall"
        ]
        >= minimum_eligible_recall
    )

    overall[
        "Maximum Recall"
    ] = maximum_recall

    overall[
        "Minimum Eligible Recall"
    ] = minimum_eligible_recall

    # ------------------------------------------------------
    # Production ranking
    # ------------------------------------------------------
    #
    # FIRST:
    #     Recall eligibility.
    #
    # THEN, within the eligible band:
    #
    #     Precision DESC
    #     Minimum Recall DESC
    #     F1 DESC
    #     FP ASC
    #     FN ASC
    #
    # Non-eligible configurations remain in the output and
    # are ranked afterward.
    #
    # Within the non-eligible group, higher recall still
    # comes first, followed by precision etc.
    # ------------------------------------------------------

    overall[
        "_eligible_sort"
    ] = (
        overall[
            "Recall Eligible"
        ]
        .astype(int)
    )

    overall = (
        overall
        .sort_values(
            by=[
                "_eligible_sort",
                "Precision",
                "Recall",
                "Minimum Recall",
                "F1",
                "FP",
                "FN",
            ],
            ascending=[
                False,
                False,
                False,
                False,
                False,
                True,
                True,
            ],
            kind="mergesort",
        )
        .copy()
    )

    # ------------------------------------------------------
    # Add rank
    # ------------------------------------------------------

    overall.insert(
        0,
        "Rank",
        range(
            1,
            len(overall) + 1,
        ),
    )

    # ------------------------------------------------------
    # Mark overall rows
    # ------------------------------------------------------

    overall.insert(
        1,
        "Test Dataset",
        "OVERALL",
    )

    # ------------------------------------------------------
    # Remove internal sorting helper
    # ------------------------------------------------------

    overall.drop(
        columns=[
            "_eligible_sort"
        ],
        inplace=True,
    )

    # ------------------------------------------------------
    # Per-dataset ranking
    # ------------------------------------------------------

    ranked = []

    for dataset_name in (
        results[
            "Test Dataset"
        ].unique()
    ):

        dataset_df = (
            results[
                results[
                    "Test Dataset"
                ]
                == dataset_name
            ]
            .sort_values(
                by=[
                    "Recall",
                    "Precision",
                    "F1",
                    "FP",
                    "FN",
                ],
                ascending=[
                    False,
                    False,
                    False,
                    True,
                    True,
                ],
                kind="mergesort",
            )
            .head(
                top_n
            )
            .copy()
        )

        dataset_df.insert(
            0,
            "Rank",
            range(
                1,
                len(dataset_df) + 1,
            ),
        )

        ranked.append(
            dataset_df
        )

    # ------------------------------------------------------
    # Combine per-dataset rankings
    # ------------------------------------------------------

    if ranked:

        per_dataset = pd.concat(
            ranked,
            ignore_index=True,
        )

    else:

        per_dataset = pd.DataFrame()

    # ------------------------------------------------------
    # Final result
    # ------------------------------------------------------

    if per_dataset.empty:

        return overall

    return pd.concat(
        [
            overall,
            per_dataset,
        ],
        ignore_index=True,
    )


# ==========================================================
# NumPy conversion helper
# ==========================================================

def to_numpy(data):
    """
    Convert pandas DataFrame/Series to NumPy array.

    Leaves NumPy arrays unchanged.
    """

    if isinstance(
        data,
        (
            pd.DataFrame,
            pd.Series,
        ),
    ):

        return data.to_numpy()

    return np.asarray(
        data
    )