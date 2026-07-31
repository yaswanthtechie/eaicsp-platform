from pathlib import Path

import pandas as pd
import pytest
from sklearn.metrics import recall_score

from src.isolation_forest_model import IsolationForestModel
from src.lof_model import LOFModel
from src.one_class_svm_model import OneClassSVMModel

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

FEATURES = [
    "temperature",
    "humidity",
    "stock_count",
]


@pytest.fixture(scope="module")
def datasets():
    train_df = pd.read_csv(OUTPUT_DIR / "train_normal.csv")
    test_df = pd.read_csv(OUTPUT_DIR / "test_combined_anomaly.csv")
    return train_df, test_df


@pytest.mark.parametrize(
    "model_cls",
    [
        IsolationForestModel,
        LOFModel,
        OneClassSVMModel,
    ],
)
def test_model_training_and_prediction(model_cls, datasets):

    train_df, test_df = datasets

    model = model_cls()

    # Train model
    model.train(train_df[FEATURES])

    # Predict
    predictions = model.predict(test_df[FEATURES])

    # Same number of predictions as samples
    assert len(predictions) == len(test_df)

    # Only sklearn anomaly labels
    assert set(predictions).issubset({-1, 1})

    # Convert to binary labels
    predicted = (predictions == -1).astype(int)
    actual = test_df["is_anomaly"]

    recall = recall_score(actual, predicted)

    # Detect at least 80% of planted anomalies
    assert recall >= 0.80