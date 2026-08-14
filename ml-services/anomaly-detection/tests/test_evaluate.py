from pathlib import Path
import sys

import pandas as pd

project_root = Path(__file__).resolve().parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.evaluate import evaluate_models

output_dir = project_root / "output"


# Helpers

def load_dataset(filename):
    return pd.read_csv(output_dir / filename)


def get_model_metric(results, model_name, metric):
    row = results.loc[results["Model"] == model_name]

    assert not row.empty, f"{model_name} not found."

    return row.iloc[0][metric]


# Evaluation Pipeline

def test_evaluate_returns_dataframe():

    df = load_dataset("test_temperature_spike.csv")

    results = evaluate_models(df)

    assert isinstance(results, pd.DataFrame)


def test_evaluate_returns_three_models():

    df = load_dataset("test_temperature_spike.csv")

    results = evaluate_models(df)

    expected = {
        "Isolation Forest",
        "One-Class SVM",
        "Local Outlier Factor",
    }

    assert set(results["Model"]) == expected


def test_evaluation_columns():

    df = load_dataset("test_temperature_spike.csv")

    results = evaluate_models(df)

    expected_columns = {
        "Model",
        "Precision",
        "Recall",
        "Caught",
        "False Alarms",
        "Predicted",
    }

    assert expected_columns.issubset(results.columns)


def test_metrics_are_valid():

    df = load_dataset("test_temperature_spike.csv")

    results = evaluate_models(df)

    assert results["Precision"].between(0, 1).all()

    assert results["Recall"].between(0, 1).all()

    assert (results["Caught"] >= 0).all()

    assert (results["False Alarms"] >= 0).all()

    assert (results["Predicted"] >= 0).all()


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


# ==========================================================
# Sanity Check
# ==========================================================

def test_all_models_detect_some_anomalies():

    df = load_dataset(
        "test_combined_anomaly.csv"
    )

    results = evaluate_models(df)

    assert (results["Predicted"] > 0).all()