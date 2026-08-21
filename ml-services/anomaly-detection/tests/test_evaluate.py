from pathlib import Path
import sys

import pandas as pd
import pytest

from src.evaluate import evaluate_models
from src.isolation_forest_model import (
    IsolationForestModel,
)
from src.lof_model import LOFModel
from src.one_class_svm_model import (
    OneClassSVMModel,
)


project_root = (
    Path(__file__).resolve().parent.parent
)

if str(project_root) not in sys.path:
    sys.path.insert(
        0,
        str(project_root),
    )


output_dir = project_root / "output"


FEATURES = [
    "temperature",
    "humidity",
    "stock_count",
]


EXPECTED_MODELS = {
    "Isolation Forest",
    "One-Class SVM",
    "Local Outlier Factor",
}


ANOMALY_DATASETS = [
    (
        "Temperature Spike",
        "test_temperature_spike.csv",
    ),
    (
        "Temperature Drift",
        "test_temperature_drift.csv",
    ),
    (
        "Stock Anomaly",
        "test_stock_anomaly.csv",
    ),
    (
        "Combined Anomaly",
        "test_combined_anomaly.csv",
    ),
]


# ============================================================
# Helpers
# ============================================================


def load_dataset(filename):
    path = output_dir / filename

    assert path.exists(), (
        f"Dataset not found: {path}"
    )

    return pd.read_csv(path)


def get_model_metric(
    results,
    model_name,
    metric,
):

    row = results.loc[
        results["Model"] == model_name
    ]

    assert not row.empty, (
        f"{model_name} not found."
    )

    return row.iloc[0][metric]


# ============================================================
# Evaluation Pipeline
# ============================================================


def test_evaluate_returns_dataframe():

    df = load_dataset(
        "test_temperature_spike.csv"
    )

    results = evaluate_models(df)

    assert isinstance(
        results,
        pd.DataFrame,
    )


def test_evaluate_returns_three_models():

    df = load_dataset(
        "test_temperature_spike.csv"
    )

    results = evaluate_models(df)

    assert set(
        results["Model"]
    ) == EXPECTED_MODELS

    assert len(results) == 3


def test_evaluation_columns():

    df = load_dataset(
        "test_temperature_spike.csv"
    )

    results = evaluate_models(df)

    expected_columns = {
        "Model",
        "Precision",
        "Recall",
        "F1",
        "Caught",
        "False Alarms",
        "Predicted",
    }

    assert expected_columns.issubset(
        results.columns
    )


def test_metrics_are_valid():

    df = load_dataset(
        "test_temperature_spike.csv"
    )

    results = evaluate_models(df)

    assert results[
        "Precision"
    ].between(
        0,
        1,
    ).all()

    assert results[
        "Recall"
    ].between(
        0,
        1,
    ).all()

    assert results[
        "F1"
    ].between(
        0,
        1,
    ).all()

    assert (
        results["Caught"] >= 0
    ).all()

    assert (
        results["False Alarms"] >= 0
    ).all()

    assert (
        results["Predicted"] >= 0
    ).all()


# ============================================================
# Evaluation Count Consistency
# ============================================================


@pytest.mark.parametrize(
    "dataset_name,filename",
    ANOMALY_DATASETS,
)
def test_evaluation_counts_are_consistent(
    dataset_name,
    filename,
):
    """
    Verify the internal consistency of the evaluation
    counters returned by evaluate.py.

    Definitions:

        Caught
            = true anomalies correctly detected
            = TP

        False Alarms
            = normal readings incorrectly detected
            = FP

        Predicted
            = all readings predicted as anomalies
            = TP + FP
    """

    df = load_dataset(filename)

    results = evaluate_models(df)

    actual_anomalies = int(
        (
            df["is_anomaly"] == 1
        ).sum()
    )

    for _, row in results.iterrows():

        caught = int(
            row["Caught"]
        )

        false_alarms = int(
            row["False Alarms"]
        )

        predicted = int(
            row["Predicted"]
        )

        assert caught >= 0

        assert false_alarms >= 0

        assert predicted >= 0

        assert predicted == (
            caught + false_alarms
        ), (
            f"Count inconsistency for "
            f"{row['Model']} on "
            f"{dataset_name}: "
            f"Predicted={predicted}, "
            f"Caught={caught}, "
            f"False Alarms={false_alarms}"
        )

        assert caught <= (
            actual_anomalies
        ), (
            f"Caught anomalies exceed "
            f"actual anomalies for "
            f"{row['Model']} on "
            f"{dataset_name}."
        )


# ============================================================
# Prediction Label Contract
# ============================================================


@pytest.mark.parametrize(
    "model_cls",
    [
        IsolationForestModel,
        LOFModel,
        OneClassSVMModel,
    ],
)
def test_model_prediction_label_contract(
    model_cls,
):
    """
    Verify the project-wide sklearn prediction convention:

        -1 = anomaly
         1 = normal
    """

    train_df = load_dataset(
        "train_normal.csv"
    )

    test_df = load_dataset(
        "test_combined_anomaly.csv"
    )

    model = model_cls()

    model.train(
        train_df[FEATURES]
    )

    predictions = model.predict(
        test_df[FEATURES]
    )

    assert len(predictions) == len(
        test_df
    )

    assert set(
        predictions
    ).issubset(
        {-1, 1}
    )


# ============================================================
# Evaluation Prediction Count Contract
# ============================================================


@pytest.mark.parametrize(
    "model_name,model_cls",
    [
        (
            "Isolation Forest",
            IsolationForestModel,
        ),
        (
            "One-Class SVM",
            OneClassSVMModel,
        ),
        (
            "Local Outlier Factor",
            LOFModel,
        ),
    ],
)
def test_evaluation_prediction_count_matches_model(
    model_name,
    model_cls,
):
    """
    Verify that evaluate.py interprets the model prediction
    correctly:

        prediction == -1
            -> anomaly
    """

    train_df = load_dataset(
        "train_normal.csv"
    )

    test_df = load_dataset(
        "test_combined_anomaly.csv"
    )

    model = model_cls()

    model.train(
        train_df[FEATURES]
    )

    raw_predictions = model.predict(
        test_df[FEATURES]
    )

    expected_predicted = int(
        (
            raw_predictions == -1
        ).sum()
    )

    results = evaluate_models(
        test_df
    )

    row = results.loc[
        results["Model"] == model_name
    ]

    assert len(row) == 1

    actual_predicted = int(
        row.iloc[0]["Predicted"]
    )

    assert (
        actual_predicted
        == expected_predicted
    )


# ============================================================
# R4 - Full 3 x 4 Model / Anomaly Coverage
# ============================================================


@pytest.mark.parametrize(
    "dataset_name,filename",
    ANOMALY_DATASETS,
)
def test_all_models_evaluated_on_each_anomaly_type(
    dataset_name,
    filename,
):
    """
    R4 coverage requirement:

        3 models x 4 anomaly types = 12 evaluations
    """

    df = load_dataset(filename)

    results = evaluate_models(df)

    assert set(
        results["Model"]
    ) == EXPECTED_MODELS, (
        f"Model coverage failed for "
        f"{dataset_name}."
    )

    assert len(results) == 3

    for model_name in EXPECTED_MODELS:

        row = results.loc[
            results["Model"] == model_name
        ]

        assert not row.empty, (
            f"{model_name} missing for "
            f"{dataset_name}."
        )

        assert row[
            "Precision"
        ].between(
            0,
            1,
        ).all(), (
            f"Invalid precision for "
            f"{model_name} on "
            f"{dataset_name}."
        )

        assert row[
            "Recall"
        ].between(
            0,
            1,
        ).all(), (
            f"Invalid recall for "
            f"{model_name} on "
            f"{dataset_name}."
        )

        assert row[
            "F1"
        ].between(
            0,
            1,
        ).all(), (
            f"Invalid F1 for "
            f"{model_name} on "
            f"{dataset_name}."
        )

        assert (
            row["Caught"] >= 0
        ).all()

        assert (
            row["False Alarms"] >= 0
        ).all()

        assert (
            row["Predicted"] >= 0
        ).all()


# ============================================================
# R4 - Explicit 12-Combination Coverage
# ============================================================


@pytest.mark.parametrize(
    "dataset_name,filename",
    ANOMALY_DATASETS,
)
@pytest.mark.parametrize(
    "model_name",
    EXPECTED_MODELS,
)
def test_each_model_has_result_for_each_anomaly_type(
    dataset_name,
    filename,
    model_name,
):
    """
    Explicitly verify every model/anomaly combination.

    Total:

        4 datasets x 3 models = 12
    """

    df = load_dataset(filename)

    results = evaluate_models(df)

    row = results.loc[
        results["Model"] == model_name
    ]

    assert len(row) == 1, (
        f"Expected exactly one result "
        f"for {model_name} on "
        f"{dataset_name}."
    )

    precision = row.iloc[0][
        "Precision"
    ]

    recall = row.iloc[0][
        "Recall"
    ]

    f1 = row.iloc[0][
        "F1"
    ]

    assert 0 <= precision <= 1, (
        f"Invalid precision for "
        f"{model_name} on "
        f"{dataset_name}: "
        f"{precision}"
    )

    assert 0 <= recall <= 1, (
        f"Invalid recall for "
        f"{model_name} on "
        f"{dataset_name}: "
        f"{recall}"
    )

    assert 0 <= f1 <= 1, (
        f"Invalid F1 for "
        f"{model_name} on "
        f"{dataset_name}: "
        f"{f1}"
    )


# ============================================================
# Benchmark Regression Tests
#
# These are regression guards for the current selected
# production candidate. They are NOT the model-selection
# algorithm.
# ============================================================


def test_lof_recall_temperature_spike():

    df = load_dataset(
        "test_temperature_spike.csv"
    )

    results = evaluate_models(df)

    recall = get_model_metric(
        results,
        "Local Outlier Factor",
        "Recall",
    )

    assert recall >= 0.95


def test_lof_recall_temperature_drift():

    df = load_dataset(
        "test_temperature_drift.csv"
    )

    results = evaluate_models(df)

    recall = get_model_metric(
        results,
        "Local Outlier Factor",
        "Recall",
    )

    assert recall >= 0.50


def test_lof_recall_stock_anomaly():

    df = load_dataset(
        "test_stock_anomaly.csv"
    )

    results = evaluate_models(df)

    recall = get_model_metric(
        results,
        "Local Outlier Factor",
        "Recall",
    )

    assert recall >= 0.95


def test_lof_recall_combined_anomaly():

    df = load_dataset(
        "test_combined_anomaly.csv"
    )

    results = evaluate_models(df)

    recall = get_model_metric(
        results,
        "Local Outlier Factor",
        "Recall",
    )

    assert recall >= 0.90


# ============================================================
# Sanity Check
# ============================================================


def test_all_models_detect_some_anomalies():

    df = load_dataset(
        "test_combined_anomaly.csv"
    )

    results = evaluate_models(df)

    assert (
        results["Predicted"] > 0
    ).all()