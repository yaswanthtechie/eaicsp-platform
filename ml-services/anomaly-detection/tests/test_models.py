from pathlib import Path

import pandas as pd
import pytest
from sklearn.metrics import recall_score

from src.isolation_forest_model import IsolationForestModel
from src.lof_model import LOFModel
from src.one_class_svm_model import OneClassSVMModel


OUTPUT_DIR = (
    Path(__file__).resolve().parent.parent
    / "output"
)


FEATURES = [
    "temperature",
    "humidity",
    "stock_count",
]


@pytest.fixture(scope="module")
def datasets():

    train_path = (
        OUTPUT_DIR
        / "train_normal.csv"
    )

    test_path = (
        OUTPUT_DIR
        / "test_combined_anomaly.csv"
    )

    assert train_path.exists(), (
        f"Training dataset not found: "
        f"{train_path}"
    )

    assert test_path.exists(), (
        f"Test dataset not found: "
        f"{test_path}"
    )

    train_df = pd.read_csv(
        train_path
    )

    test_df = pd.read_csv(
        test_path
    )

    return train_df, test_df


@pytest.mark.parametrize(
    "model_cls",
    [
        IsolationForestModel,
        LOFModel,
        OneClassSVMModel,
    ],
)
def test_model_training_and_prediction(
    model_cls,
    datasets,
):

    train_df, test_df = datasets

    # --------------------------------------------------------
    # Verify required columns
    # --------------------------------------------------------

    assert all(
        column in train_df.columns
        for column in FEATURES
    )

    assert all(
        column in test_df.columns
        for column in FEATURES
    )

    assert "is_anomaly" in test_df.columns

    # --------------------------------------------------------
    # Verify that the test dataset actually contains
    # planted anomalies.
    # --------------------------------------------------------

    actual = (
        test_df["is_anomaly"]
        .to_numpy()
        .astype(int)
    )

    assert actual.sum() > 0, (
        "Combined anomaly test dataset "
        "contains no anomalies."
    )

    # --------------------------------------------------------
    # Create model
    # --------------------------------------------------------

    model = model_cls()

    # --------------------------------------------------------
    # Train only on normal training data
    # --------------------------------------------------------

    model.train(
        train_df[FEATURES]
    )

    # --------------------------------------------------------
    # Predict
    # --------------------------------------------------------

    predictions = model.predict(
        test_df[FEATURES]
    )

    # --------------------------------------------------------
    # Prediction count must match test samples
    # --------------------------------------------------------

    assert len(predictions) == len(
        test_df
    )

    # --------------------------------------------------------
    # sklearn anomaly labels must be:
    #
    #     -1 = anomaly
    #      1 = normal
    # --------------------------------------------------------

    assert set(
        predictions
    ).issubset({-1, 1})

    # --------------------------------------------------------
    # Convert to binary anomaly labels
    #
    #     1 = anomaly
    #     0 = normal
    # --------------------------------------------------------

    predicted = (
        predictions == -1
    ).astype(int)

    # --------------------------------------------------------
    # Recall
    # --------------------------------------------------------

    recall = recall_score(
        actual,
        predicted,
        zero_division=0,
    )

    # --------------------------------------------------------
    # Production-oriented minimum recall requirement
    # --------------------------------------------------------

    assert recall >= 0.80, (
        f"{model_cls.__name__} recall "
        f"{recall:.4f} is below the "
        f"required minimum of 0.80."
    )