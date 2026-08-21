import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sklearn.svm import OneClassSVM

from src import cost_threshold_tuning as ctt


# ============================================================
# Helpers
# ============================================================

class DecisionFunctionModel:
    """
    Minimal sklearn-like model used to test the project's
    anomaly-score convention.

    Native decision_function:
        higher = more normal
        lower = more anomalous
    """

    def __init__(self, decision_scores):
        self.decision_scores = np.asarray(
            decision_scores,
            dtype=float,
        )

    def decision_function(self, features):
        return self.decision_scores

    def predict(self, features):
        # Native sklearn convention:
        # -1 = anomaly
        # +1 = normal
        return np.where(
            self.decision_scores < 0,
            -1,
            1,
        )


class ScoreWrapper:
    """
    Project-style wrapper exposing score().
    """

    def __init__(self, raw_scores):
        self.raw_scores = np.asarray(
            raw_scores,
            dtype=float,
        )

    def score(self, features):
        return self.raw_scores

    def predict(self, features):
        return np.where(
            self.raw_scores < 0,
            -1,
            1,
        )


class ModelWrapper:
    """
    Project-style wrapper containing a fitted sklearn-like
    estimator as .model.
    """

    def __init__(self, raw_scores):
        self.model = DecisionFunctionModel(
            raw_scores
        )

    def predict(self, features):
        return self.model.predict(
            features
        )


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def feature_dataframe():
    return pd.DataFrame(
        {
            "temperature": [
                20.0,
                21.0,
                22.0,
                30.0,
            ],
            "humidity": [
                40.0,
                42.0,
                41.0,
                70.0,
            ],
            "stock_count": [
                100,
                101,
                99,
                20,
            ],
            "is_anomaly": [
                0,
                0,
                0,
                1,
            ],
        }
    )


@pytest.fixture
def four_point_dataset():
    return pd.DataFrame(
        {
            "temperature": [
                20.0,
                21.0,
                22.0,
                30.0,
            ],
            "humidity": [
                40.0,
                42.0,
                41.0,
                70.0,
            ],
            "stock_count": [
                100,
                101,
                99,
                20,
            ],
            "is_anomaly": [
                0,
                0,
                0,
                1,
            ],
        }
    )


# ============================================================
# Test 1
# Project anomaly score convention
# ============================================================

def test_get_anomaly_scores_inverts_decision_function():
    """
    The project explicitly defines:

        anomaly_score = -decision_function()

    Therefore:

        decision_function = [-0.8, 0.2, 0.7]

    becomes:

        anomaly_score = [0.8, -0.2, -0.7]
    """

    model = DecisionFunctionModel(
        [-0.8, 0.2, 0.7]
    )

    features = np.zeros(
        (3, 3)
    )

    scores = ctt.get_anomaly_scores(
        model,
        features,
    )

    expected = np.array(
        [0.8, -0.2, -0.7]
    )

    np.testing.assert_allclose(
        scores,
        expected,
    )


# ============================================================
# Test 2
# Higher score means more anomalous
# ============================================================

def test_higher_project_score_is_more_anomalous():
    model = DecisionFunctionModel(
        [-0.9, 0.0, 0.8]
    )

    features = np.zeros(
        (3, 3)
    )

    scores = ctt.get_anomaly_scores(
        model,
        features,
    )

    assert scores[0] > scores[1]
    assert scores[1] > scores[2] or scores[2] < scores[1]


# ============================================================
# Test 3
# score() wrapper is supported
# ============================================================

def test_wrapper_score_is_inverted():
    """
    Wrapper score() represents the underlying decision
    function, so it must also be inverted.
    """

    model = ScoreWrapper(
        [-0.5, 0.1, 0.9]
    )

    features = np.zeros(
        (3, 3)
    )

    scores = ctt.get_anomaly_scores(
        model,
        features,
    )

    expected = np.array(
        [0.5, -0.1, -0.9]
    )

    np.testing.assert_allclose(
        scores,
        expected,
    )


# ============================================================
# Test 4
# .model.decision_function() fallback
# ============================================================

def test_model_wrapper_decision_function_is_supported():
    model = ModelWrapper(
        [-0.4, 0.2, 0.7]
    )

    features = np.zeros(
        (3, 3)
    )

    scores = ctt.get_anomaly_scores(
        model,
        features,
    )

    expected = np.array(
        [0.4, -0.2, -0.7]
    )

    np.testing.assert_allclose(
        scores,
        expected,
    )


# ============================================================
# Test 5
# Unsupported model raises AttributeError
# ============================================================

def test_get_anomaly_scores_rejects_unsupported_model():
    class UnsupportedModel:
        pass

    model = UnsupportedModel()

    features = np.zeros(
        (2, 3)
    )

    with pytest.raises(
        AttributeError,
        match="does not expose",
    ):
        ctt.get_anomaly_scores(
            model,
            features,
        )


# ============================================================
# Test 6
# Non-finite scores are rejected
# ============================================================

def test_non_finite_decision_scores_are_rejected():
    model = DecisionFunctionModel(
        [
            -0.5,
            np.nan,
            0.5,
        ]
    )

    features = np.zeros(
        (3, 3)
    )

    with pytest.raises(
        ValueError,
        match="non-finite",
    ):
        ctt.get_anomaly_scores(
            model,
            features,
        )


# ============================================================
# Test 7
# Native predictions use sklearn convention
# ============================================================

def test_reference_predictions_convert_minus_one_to_anomaly():
    model = DecisionFunctionModel(
        [-0.8, 0.1, -0.2, 0.5]
    )

    features = np.zeros(
        (4, 3)
    )

    predictions = (
        ctt.get_reference_predictions(
            model,
            features,
        )
    )

    expected = np.array(
        [1, 0, 1, 0]
    )

    np.testing.assert_array_equal(
        predictions,
        expected,
    )


# ============================================================
# Test 8
# Threshold direction
# ============================================================

def test_threshold_higher_score_means_anomaly():
    scores = np.array(
        [
            -0.5,
            0.0,
            0.5,
            1.0,
        ]
    )

    y_true = np.array(
        [
            0,
            0,
            1,
            1,
        ]
    )

    result = ctt.evaluate_threshold(
        scores=scores,
        y_true=y_true,
        threshold=0.25,
    )

    # 0.5 and 1.0 are anomalies.
    assert result["TP"] == 2
    assert result["FP"] == 0
    assert result["FN"] == 0
    assert result["TN"] == 2

    assert result["Precision"] == 1.0
    assert result["Recall"] == 1.0
    assert result["F1"] == 1.0


# ============================================================
# Test 9
# Business cost calculation
# ============================================================

def test_expected_business_cost():
    """
    FP cost = 2
    FN cost = 500

    Example:
        FP = 3
        FN = 2

    Cost:
        3*2 + 2*500
        = 1006
    """

    scores = np.array(
        [
            0.8,
            0.7,
            0.6,
            0.1,
            0.0,
        ]
    )

    y_true = np.array(
        [
            1,
            1,
            0,
            0,
            1,
        ]
    )

    result = ctt.evaluate_threshold(
        scores=scores,
        y_true=y_true,
        threshold=0.65,
    )

    # Predictions:
    # 0.8 -> anomaly, TP
    # 0.7 -> anomaly, TP
    # 0.6 -> normal, FP? no, true normal
    # 0.1 -> normal, true normal
    # 0.0 -> normal, FN
    #
    # TP = 2
    # FP = 0
    # FN = 1
    #
    # Cost = 0*2 + 1*500 = 500

    assert result["TP"] == 2
    assert result["FP"] == 0
    assert result["FN"] == 1

    assert result["Expected Cost"] == 500


# ============================================================
# Test 10
# Threshold grid is sorted and unique
# ============================================================

def test_build_thresholds_returns_unique_thresholds():
    scores = np.array(
        [
            -1.0,
            -0.5,
            0.0,
            0.5,
            1.0,
        ]
    )

    thresholds = ctt.build_thresholds(
        scores,
        max_thresholds=20,
    )

    assert len(thresholds) > 0

    assert np.all(
        np.diff(thresholds) >= 0
    )

    assert len(thresholds) == len(
        np.unique(thresholds)
    )


# ============================================================
# Test 11
# Threshold grid covers outside score range
# ============================================================

def test_threshold_grid_has_outside_boundaries():
    scores = np.array(
        [
            -1.0,
            0.0,
            1.0,
        ]
    )

    thresholds = ctt.build_thresholds(
        scores,
        max_thresholds=20,
    )

    assert thresholds[0] < scores.min()
    assert thresholds[-1] > scores.max()


# ============================================================
# Test 12
# Reference threshold reproduces native predictions
# ============================================================

def test_reference_threshold_agrees_with_native_prediction():
    scores = np.array(
        [
            0.9,
            0.8,
            0.2,
            -0.1,
            -0.5,
        ]
    )

    native_predictions = np.array(
        [
            1,
            1,
            0,
            0,
            0,
        ]
    )

    threshold, agreement = (
        ctt.calculate_reference_threshold(
            scores,
            native_predictions,
        )
    )

    predicted = (
        scores >= threshold
    ).astype(int)

    assert agreement == 1.0

    np.testing.assert_array_equal(
        predicted,
        native_predictions,
    )


# ============================================================
# Test 13
# Primary dataset definition
# ============================================================

def test_drift_is_not_a_primary_cost_dataset():
    assert "temperature_drift" not in (
        ctt.PRIMARY_DATASETS
    )

    assert (
        ctt.PRIMARY_DATASETS
        ==
        [
            "temperature_spike",
            "stock_anomaly",
            "combined_anomaly",
        ]
    )


# ============================================================
# Test 14
# Primary aggregation excludes drift
# ============================================================

def test_aggregate_primary_cost_excludes_drift():
    model_results = pd.DataFrame(
        [
            {
                "Model": "Test Model",
                "Score Direction":
                    "higher_is_anomaly",
                "Native Threshold": 0.5,
                "Direction Agreement": 1.0,
                "Threshold": 0.5,
                "Test Dataset":
                    "temperature_spike",
                "TP": 10,
                "TN": 90,
                "FP": 2,
                "FN": 0,
            },
            {
                "Model": "Test Model",
                "Score Direction":
                    "higher_is_anomaly",
                "Native Threshold": 0.5,
                "Direction Agreement": 1.0,
                "Threshold": 0.5,
                "Test Dataset":
                    "stock_anomaly",
                "TP": 8,
                "TN": 92,
                "FP": 3,
                "FN": 1,
            },
            {
                "Model": "Test Model",
                "Score Direction":
                    "higher_is_anomaly",
                "Native Threshold": 0.5,
                "Direction Agreement": 1.0,
                "Threshold": 0.5,
                "Test Dataset":
                    "combined_anomaly",
                "TP": 9,
                "TN": 91,
                "FP": 4,
                "FN": 2,
            },
            {
                "Model": "Test Model",
                "Score Direction":
                    "higher_is_anomaly",
                "Native Threshold": 0.5,
                "Direction Agreement": 1.0,
                "Threshold": 0.5,
                "Test Dataset":
                    "temperature_drift",
                "TP": 1,
                "TN": 1,
                "FP": 1000,
                "FN": 1000,
            },
        ]
    )

    result = (
        ctt.aggregate_primary_cost(
            model_results
        )
    )

    assert len(result) == 1

    row = result.iloc[0]

    # Only primary datasets:
    #
    # TP = 10 + 8 + 9 = 27
    # FP = 2 + 3 + 4 = 9
    # FN = 0 + 1 + 2 = 3

    assert row["TP"] == 27
    assert row["FP"] == 9
    assert row["FN"] == 3

    # Cost:
    #
    # 9*2 + 3*500 = 1518

    assert row["Expected Cost"] == 1518


# ============================================================
# Test 15
# Aggregate precision and recall
# ============================================================

def test_primary_aggregate_metrics_are_calculated_from_counts():
    model_results = pd.DataFrame(
        [
            {
                "Model": "Test Model",
                "Score Direction":
                    "higher_is_anomaly",
                "Native Threshold": 0.5,
                "Direction Agreement": 1.0,
                "Threshold": 0.5,
                "Test Dataset":
                    "temperature_spike",
                "TP": 8,
                "TN": 90,
                "FP": 2,
                "FN": 2,
            },
            {
                "Model": "Test Model",
                "Score Direction":
                    "higher_is_anomaly",
                "Native Threshold": 0.5,
                "Direction Agreement": 1.0,
                "Threshold": 0.5,
                "Test Dataset":
                    "stock_anomaly",
                "TP": 9,
                "TN": 90,
                "FP": 1,
                "FN": 1,
            },
            {
                "Model": "Test Model",
                "Score Direction":
                    "higher_is_anomaly",
                "Native Threshold": 0.5,
                "Direction Agreement": 1.0,
                "Threshold": 0.5,
                "Test Dataset":
                    "combined_anomaly",
                "TP": 10,
                "TN": 89,
                "FP": 1,
                "FN": 0,
            },
        ]
    )

    result = (
        ctt.aggregate_primary_cost(
            model_results
        )
    )

    row = result.iloc[0]

    # TP = 27
    # FP = 4
    # FN = 3

    expected_precision = (
        27 / 31
    )

    expected_recall = (
        27 / 30
    )

    assert row["Precision"] == pytest.approx(
        expected_precision
    )

    assert row["Recall"] == pytest.approx(
        expected_recall
    )


# ============================================================
# Test 16
# Cost-optimal selection prioritizes cost
# ============================================================

def test_cost_optimal_threshold_prioritizes_cost():
    primary_results = pd.DataFrame(
        [
            {
                "Threshold": 0.10,
                "Expected Cost": 100,
                "Recall": 0.90,
                "Precision": 0.95,
                "F1": 0.92,
                "FP": 0,
                "FN": 0,
            },
            {
                "Threshold": 0.20,
                "Expected Cost": 50,
                "Recall": 0.80,
                "Precision": 0.99,
                "F1": 0.88,
                "FP": 0,
                "FN": 0,
            },
        ]
    )

    selected = (
        ctt.select_cost_optimal_threshold(
            primary_results
        )
    )

    assert selected["Threshold"] == 0.20


# ============================================================
# Test 17
# Recall breaks cost ties
# ============================================================

def test_cost_optimal_threshold_uses_recall_as_first_tiebreak():
    primary_results = pd.DataFrame(
        [
            {
                "Threshold": 0.10,
                "Expected Cost": 100,
                "Recall": 0.80,
                "Precision": 0.95,
                "F1": 0.87,
                "FP": 10,
                "FN": 1,
            },
            {
                "Threshold": 0.20,
                "Expected Cost": 100,
                "Recall": 0.90,
                "Precision": 0.80,
                "F1": 0.85,
                "FP": 20,
                "FN": 0,
            },
        ]
    )

    selected = (
        ctt.select_cost_optimal_threshold(
            primary_results
        )
    )

    assert selected["Threshold"] == 0.20


# ============================================================
# Test 18
# Precision breaks remaining tie
# ============================================================

def test_cost_optimal_threshold_uses_precision_after_recall():
    primary_results = pd.DataFrame(
        [
            {
                "Threshold": 0.10,
                "Expected Cost": 100,
                "Recall": 0.90,
                "Precision": 0.80,
                "F1": 0.85,
                "FP": 20,
                "FN": 0,
            },
            {
                "Threshold": 0.20,
                "Expected Cost": 100,
                "Recall": 0.90,
                "Precision": 0.90,
                "F1": 0.89,
                "FP": 10,
                "FN": 0,
            },
        ]
    )

    selected = (
        ctt.select_cost_optimal_threshold(
            primary_results
        )
    )

    assert selected["Threshold"] == 0.20


# ============================================================
# Test 19
# F1 selector is independent from cost selector
# ============================================================

def test_f1_optimal_threshold_selects_highest_f1():
    primary_results = pd.DataFrame(
        [
            {
                "Threshold": 0.10,
                "Expected Cost": 500,
                "Recall": 1.00,
                "Precision": 0.40,
                "F1": 0.5714,
            },
            {
                "Threshold": 0.20,
                "Expected Cost": 1000,
                "Recall": 0.90,
                "Precision": 0.90,
                "F1": 0.895,
            },
        ]
    )

    selected = (
        ctt.select_f1_optimal_threshold(
            primary_results
        )
    )

    assert selected["Threshold"] == 0.20


# ============================================================
# Test 20
# Evaluate threshold with all anomalies missed
# ============================================================

def test_threshold_can_produce_false_negatives():
    scores = np.array(
        [
            0.1,
            0.2,
            0.3,
            0.4,
        ]
    )

    y_true = np.array(
        [
            0,
            0,
            1,
            1,
        ]
    )

    result = ctt.evaluate_threshold(
        scores,
        y_true,
        threshold=0.9,
    )

    assert result["TP"] == 0
    assert result["FP"] == 0
    assert result["FN"] == 2

    assert result["Expected Cost"] == (
        2 * ctt.COST_FN
    )


# ============================================================
# Test 21
# Evaluate threshold with all readings anomalous
# ============================================================

def test_threshold_can_produce_false_positives():
    scores = np.array(
        [
            0.9,
            0.8,
            0.7,
            0.6,
        ]
    )

    y_true = np.array(
        [
            0,
            0,
            1,
            1,
        ]
    )

    result = ctt.evaluate_threshold(
        scores,
        y_true,
        threshold=0.5,
    )

    assert result["TP"] == 2
    assert result["FP"] == 2
    assert result["FN"] == 0

    assert result["Expected Cost"] == (
        2 * ctt.COST_FP
    )


# ============================================================
# Test 22
# Primary aggregation uses one common threshold
# ============================================================

def test_primary_aggregation_groups_by_threshold():
    model_results = pd.DataFrame(
        [
            {
                "Model": "Test",
                "Score Direction":
                    "higher_is_anomaly",
                "Native Threshold": 0.0,
                "Direction Agreement": 1.0,
                "Threshold": 0.10,
                "Test Dataset":
                    "temperature_spike",
                "TP": 10,
                "TN": 90,
                "FP": 1,
                "FN": 0,
            },
            {
                "Model": "Test",
                "Score Direction":
                    "higher_is_anomaly",
                "Native Threshold": 0.0,
                "Direction Agreement": 1.0,
                "Threshold": 0.10,
                "Test Dataset":
                    "stock_anomaly",
                "TP": 10,
                "TN": 90,
                "FP": 1,
                "FN": 0,
            },
            {
                "Model": "Test",
                "Score Direction":
                    "higher_is_anomaly",
                "Native Threshold": 0.0,
                "Direction Agreement": 1.0,
                "Threshold": 0.10,
                "Test Dataset":
                    "combined_anomaly",
                "TP": 10,
                "TN": 90,
                "FP": 1,
                "FN": 0,
            },
        ]
    )

    result = (
        ctt.aggregate_primary_cost(
            model_results
        )
    )

    assert len(result) == 1
    assert result.iloc[0]["Threshold"] == 0.10


# ============================================================
# Test 23
# Full model threshold result generation
# ============================================================

def test_create_model_threshold_results(
    four_point_dataset,
):
    model = DecisionFunctionModel(
        [
            0.8,
            0.1,
            0.0,
            -0.7,
        ]
    )

    datasets = {
        "temperature_spike":
            four_point_dataset,

        "temperature_drift":
            four_point_dataset,

        "stock_anomaly":
            four_point_dataset,

        "combined_anomaly":
            four_point_dataset,
    }

    results = (
        ctt.create_model_threshold_results(
            model=model,
            model_name="Test Model",
            datasets=datasets,
        )
    )

    assert not results.empty

    expected_columns = {
        "Model",
        "Test Dataset",
        "Score Direction",
        "Native Threshold",
        "Direction Agreement",
        "Threshold",
        "Precision",
        "Recall",
        "F1",
        "TP",
        "TN",
        "FP",
        "FN",
        "Expected Cost",
    }

    assert expected_columns.issubset(
        results.columns
    )

    assert set(
        results["Test Dataset"].unique()
    ) == set(
        datasets.keys()
    )

    assert set(
        results["Score Direction"].unique()
    ) == {
        "higher_is_anomaly"
    }


# ============================================================
# Test 24
# Native predict agreement should be perfect for the
# synthetic test model
# ============================================================

def test_create_model_results_has_native_prediction_agreement(
    four_point_dataset,
):
    model = DecisionFunctionModel(
        [
            -0.8,
            -0.2,
            0.3,
            0.9,
        ]
    )

    datasets = {
        "temperature_spike":
            four_point_dataset,

        "temperature_drift":
            four_point_dataset,

        "stock_anomaly":
            four_point_dataset,

        "combined_anomaly":
            four_point_dataset,
    }

    results = (
        ctt.create_model_threshold_results(
            model,
            "Test Model",
            datasets,
        )
    )

    agreements = (
        results[
            "Direction Agreement"
        ].unique()
    )

    assert len(agreements) == 1

    assert agreements[0] == pytest.approx(
        1.0
    )


# ============================================================
# Test 25
# Empty primary results are rejected
# ============================================================

def test_select_cost_optimal_threshold_rejects_empty_results():
    with pytest.raises(
        RuntimeError,
        match="No primary threshold results",
    ):
        ctt.select_cost_optimal_threshold(
            pd.DataFrame()
        )


# ============================================================
# Test 26
# One-class score grid is rejected
# ============================================================

def test_build_thresholds_rejects_single_unique_score():
    scores = np.array(
        [
            0.5,
            0.5,
            0.5,
            0.5,
        ]
    )

    with pytest.raises(
        ValueError,
        match="fewer than two unique scores",
    ):
        ctt.build_thresholds(
            scores
        )


# ============================================================
# Test 27
# Configuration constants
# ============================================================

def test_business_cost_configuration():
    assert ctt.COST_FP == 2
    assert ctt.COST_FN == 500


# ============================================================
# Test 28
# Feature configuration
# ============================================================

def test_feature_columns_are_correct():
    assert ctt.FEATURE_COLUMNS == [
        "temperature",
        "humidity",
        "stock_count",
    ]


# ============================================================
# Test 29
# All required anomaly datasets are configured
# ============================================================

def test_all_required_datasets_are_configured():
    expected = {
        "temperature_spike",
        "temperature_drift",
        "stock_anomaly",
        "combined_anomaly",
    }

    assert set(
        ctt.DATASETS.keys()
    ) == expected


# ============================================================
# Test 30
# All three production models are configured
# ============================================================

def test_all_three_models_are_configured():
    expected = {
        "Isolation Forest",
        "One-Class SVM",
        "Local Outlier Factor",
    }

    assert set(
        ctt.MODEL_FILES.keys()
    ) == expected