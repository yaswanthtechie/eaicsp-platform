from pathlib import Path

import pandas as pd
import pytest

from src.tuning_utils import (
    SELECTION_DATASETS,
    RECALL_TOLERANCE,
    rank_results,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"


MODELS = {
    "Isolation Forest",
    "One-Class SVM",
    "Local Outlier Factor",
}

DATASETS = {
    "temperature_spike",
    "temperature_drift",
    "stock_anomaly",
    "combined_anomaly",
}


def make_result(
    model,
    dataset,
    precision,
    recall,
    f1,
    fp,
    fn,
    parameter,
):
    return {
        "Model": model,
        "Test Dataset": dataset,
        "Precision": precision,
        "Recall": recall,
        "PR Score": (precision + recall) / 2,
        "F1": f1,
        "TP": 20,
        "TN": 4980,
        "FP": fp,
        "FN": fn,
        "Parameter": parameter,
    }


# =====================================================================
# DATASET / CONFIGURATION
# =====================================================================

def test_selection_datasets_are_correct():

    assert set(SELECTION_DATASETS) == {
        "temperature_spike",
        "stock_anomaly",
        "combined_anomaly",
    }

    assert "temperature_drift" not in (
        SELECTION_DATASETS
    )


@pytest.mark.parametrize(
    "filename",
    [
        "train_normal.csv",
        "test_temperature_spike.csv",
        "test_temperature_drift.csv",
        "test_stock_anomaly.csv",
        "test_combined_anomaly.csv",
    ],
)
def test_required_tuning_dataset_exists(filename):

    assert (
        OUTPUT_DIR / filename
    ).exists()


@pytest.mark.parametrize(
    "filename",
    [
        "test_temperature_spike.csv",
        "test_temperature_drift.csv",
        "test_stock_anomaly.csv",
        "test_combined_anomaly.csv",
    ],
)
def test_anomaly_dataset_structure(filename):

    df = pd.read_csv(
        OUTPUT_DIR / filename
    )

    assert {
        "temperature",
        "humidity",
        "stock_count",
        "is_anomaly",
    }.issubset(df.columns)

    assert len(df) > 0
    assert df["is_anomaly"].sum() > 0


# =====================================================================
# RANKING
# =====================================================================

def test_rank_results_returns_overall_results():

    rows = []

    for dataset in SELECTION_DATASETS:

        rows.append(
            make_result(
                "Isolation Forest",
                dataset,
                0.80,
                1.00,
                0.88,
                5,
                0,
                "A",
            )
        )

        rows.append(
            make_result(
                "Isolation Forest",
                dataset,
                0.90,
                0.98,
                0.93,
                3,
                1,
                "B",
            )
        )

    results = rank_results(rows)

    overall = results[
        results["Test Dataset"] == "OVERALL"
    ]

    assert len(overall) == 2
    assert set(overall["Parameter"]) == {
        "A",
        "B",
    }


def test_recall_eligibility_is_applied():

    rows = []

    for dataset in SELECTION_DATASETS:

        rows.append(
            make_result(
                "Test Model",
                dataset,
                0.80,
                1.00,
                0.88,
                5,
                0,
                "ELIGIBLE",
            )
        )

        rows.append(
            make_result(
                "Test Model",
                dataset,
                1.00,
                0.50,
                0.66,
                0,
                10,
                "INELIGIBLE",
            )
        )

    results = rank_results(
        rows,
        recall_tolerance=RECALL_TOLERANCE,
    )

    overall = results[
        results["Test Dataset"] == "OVERALL"
    ]

    eligible = overall[
        overall["Parameter"] == "ELIGIBLE"
    ].iloc[0]

    ineligible = overall[
        overall["Parameter"] == "INELIGIBLE"
    ].iloc[0]

    assert bool(
        eligible["Recall Eligible"]
    )

    assert not bool(
        ineligible["Recall Eligible"]
    )


def test_eligible_configuration_with_better_precision_wins():

    rows = []

    for dataset in SELECTION_DATASETS:

        rows.append(
            make_result(
                "Test Model",
                dataset,
                0.60,
                1.00,
                0.75,
                10,
                0,
                "HIGH_RECALL",
            )
        )

        rows.append(
            make_result(
                "Test Model",
                dataset,
                0.90,
                0.98,
                0.93,
                3,
                1,
                "HIGH_PRECISION",
            )
        )

    results = rank_results(
        rows,
        recall_tolerance=0.02,
    )

    overall = (
        results[
            results["Test Dataset"]
            == "OVERALL"
        ]
        .sort_values("Rank")
    )

    assert (
        overall.iloc[0]["Parameter"]
        == "HIGH_PRECISION"
    )


def test_temperature_drift_does_not_affect_overall_selection():

    rows = []

    for dataset in SELECTION_DATASETS:

        rows.append(
            make_result(
                "Test Model",
                dataset,
                0.80,
                1.00,
                0.88,
                5,
                0,
                "A",
            )
        )

    rows.append(
        make_result(
            "Test Model",
            "temperature_drift",
            0.01,
            0.01,
            0.01,
            1000,
            1000,
            "A",
        )
    )

    results = rank_results(rows)

    overall = results[
        results["Test Dataset"] == "OVERALL"
    ]

    assert len(overall) == 1
    assert overall.iloc[0]["Model"] == (
        "Test Model"
    )


# =====================================================================
# RESULT SANITY
# =====================================================================

def test_ranking_metrics_are_valid():

    rows = []

    for dataset in DATASETS:

        rows.append(
            make_result(
                "Isolation Forest",
                dataset,
                0.80,
                0.90,
                0.85,
                10,
                2,
                "A",
            )
        )

    results = rank_results(rows)

    for column in [
        "Precision",
        "Recall",
        "F1",
    ]:

        values = results[column].dropna()

        assert values.between(
            0,
            1,
        ).all()

    for column in [
        "TP",
        "TN",
        "FP",
        "FN",
    ]:

        values = results[column].dropna()

        assert (
            values >= 0
        ).all()


def test_r4_model_and_dataset_contract():

    assert len(MODELS) == 3
    assert len(DATASETS) == 4

    assert MODELS == {
        "Isolation Forest",
        "One-Class SVM",
        "Local Outlier Factor",
    }