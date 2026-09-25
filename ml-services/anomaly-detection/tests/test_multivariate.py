"""
M3 - relationship anomalies: each feature normal, combination abnormal.
"""

import pytest

from src.data import (
    generate_correlated_normal_data,
    inject_relationship_breaks,
)
from src.multivariate_eval import (
    FEATURES,
    build_datasets,
    evaluate_relationship_detection,
)


@pytest.fixture(scope="module")
def datasets():
    return build_datasets()


@pytest.fixture(scope="module")
def results(datasets):
    train_df, test_df = datasets
    return evaluate_relationship_detection(train_df, test_df).set_index("Model")


def test_normal_data_has_the_relationship():
    df = generate_correlated_normal_data(n=5000, seed=42)

    assert df["temperature"].corr(df["humidity"]) < -0.6


def test_relationship_breaks_are_individually_normal(datasets):
    train_df, test_df = datasets

    anomalies = test_df[test_df["is_anomaly"] == 1]

    z = (
        (anomalies[["temperature", "humidity"]] - train_df[["temperature", "humidity"]].mean())
        / train_df[["temperature", "humidity"]].std()
    ).abs()

    # This is what makes it an M3 case: no single value is extreme.
    assert (z <= 2.1).all().all()


def test_single_feature_rule_cannot_see_relationship_breaks(results):
    assert results.loc["Univariate z-score (baseline)", "Caught"] == 0


def test_a_multivariate_model_catches_relationship_breaks(results):
    assert results.loc["LOF", "Recall"] >= 0.9
    assert results.loc["Elliptic Envelope", "Recall"] >= 0.9


def test_injection_is_reproducible():
    base = generate_correlated_normal_data(n=500, seed=1)

    first = inject_relationship_breaks(base, 10, seed=7)
    second = inject_relationship_breaks(base, 10, seed=7)

    assert first[FEATURES].equals(second[FEATURES])