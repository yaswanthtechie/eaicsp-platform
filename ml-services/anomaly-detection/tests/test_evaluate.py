from pathlib import Path
import sys

import pandas as pd
import pytest


project_root = Path(__file__).resolve().parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


from src.evaluate import evaluate_models


output_dir = project_root / "output"

# Helpers

def load_dataset(filename):
    return pd.read_csv(output_dir / filename)


def get_model_metric(results, model_name, metric):
    row = results.loc[
        results["Model"] == model_name
    ]

    assert not row.empty, f"{model_name} not found."

    return row.iloc[0][metric]


# Evaluation Pipeline

def test_evaluate_returns_dataframe():

    df = load_dataset(
        "test_temperature_spike.csv"
    )

    results = evaluate_models(df)

    assert isinstance(results, pd.DataFrame)


def test_evaluate_returns_three_models():

    df = load_dataset(
        "test_temperature_spike.csv"
    )

    results = evaluate_models(df)

    expected = {
        "Isolation Forest",
        "One-Class SVM",
        "Local Outlier Factor",
    }

    assert set(results["Model"]) == expected


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

    assert results["Precision"].between(
        0, 1
    ).all()

    assert results["Recall"].between(
        0, 1
    ).all()

    assert results["F1"].between(
        0, 1
    ).all()

    assert (results["Caught"] >= 0).all()

    assert (
        results["False Alarms"] >= 0
    ).all()

    assert (
        results["Predicted"] >= 0
    ).all()


# R4 - Full 3 x 4 Model / Anomaly Coverage

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


EXPECTED_MODELS = {
    "Isolation Forest",
    "One-Class SVM",
    "Local Outlier Factor",
}


@pytest.mark.parametrize(
    "dataset_name,filename",
    ANOMALY_DATASETS,
)
def test_all_models_evaluated_on_each_anomaly_type(
    dataset_name,
    filename,
):
    """
    Verify that all three anomaly detection models
    are evaluated against every anomaly dataset.

    R4 coverage requirement:

        3 models x 4 anomaly types = 12 evaluations
    """

    df = load_dataset(filename)

    results = evaluate_models(df)

    # Verify all three models are present.
    assert set(results["Model"]) == EXPECTED_MODELS, (
        f"Model coverage failed for {dataset_name}."
    )

    # Exactly three model results should be returned.
    assert len(results) == 3

    # Verify every model has valid evaluation metrics.
    for model_name in EXPECTED_MODELS:

        row = results.loc[
            results["Model"] == model_name
        ]

        assert not row.empty, (
            f"{model_name} missing for "
            f"{dataset_name}."
        )

        assert row["Precision"].between(
            0, 1
        ).all(), (
            f"Invalid precision for "
            f"{model_name} on {dataset_name}."
        )

        assert row["Recall"].between(
            0, 1
        ).all(), (
            f"Invalid recall for "
            f"{model_name} on {dataset_name}."
        )

        assert row["F1"].between(
            0, 1
        ).all(), (
            f"Invalid F1 for "
            f"{model_name} on {dataset_name}."
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


# R4 - Explicit 12-Combination Coverage

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

    Total checks:

        4 datasets x 3 models = 12
    """

    df = load_dataset(filename)

    results = evaluate_models(df)

    row = results.loc[
        results["Model"] == model_name
    ]

    assert len(row) == 1, (
        f"Expected exactly one result for "
        f"{model_name} on {dataset_name}."
    )

    precision = row.iloc[0]["Precision"]
    recall = row.iloc[0]["Recall"]
    f1 = row.iloc[0]["F1"]

    assert 0 <= precision <= 1, (
        f"Invalid precision for "
        f"{model_name} on {dataset_name}: "
        f"{precision}"
    )

    assert 0 <= recall <= 1, (
        f"Invalid recall for "
        f"{model_name} on {dataset_name}: "
        f"{recall}"
    )

    assert 0 <= f1 <= 1, (
        f"Invalid F1 for "
        f"{model_name} on {dataset_name}: "
        f"{f1}"
    )


# Benchmark Regression Tests

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


# Sanity Check

def test_all_models_detect_some_anomalies():

    df = load_dataset(
        "test_combined_anomaly.csv"
    )

    results = evaluate_models(df)

    assert (
        results["Predicted"] > 0
    ).all()