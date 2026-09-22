"""
M3 - multivariate (relationship) anomaly evaluation.

Trains fresh models on CORRELATED normal data and checks whether
they catch relationship breaks that no single-feature rule can
see. This is an experiment script: it never touches the deployed
models in models/.

Run from the service root:
    python -m src.multivariate_eval
"""

import numpy as np
import pandas as pd
from sklearn.covariance import EllipticEnvelope
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.preprocessing import StandardScaler

from src.data import (
    generate_correlated_normal_data,
    inject_relationship_breaks,
)
from src.isolation_forest_model import IsolationForestModel
from src.lof_model import LOFModel
from src.one_class_svm_model import OneClassSVMModel


FEATURES = ["temperature", "humidity", "stock_count"]

RANDOM_SEED = 42
TRAIN_SEED = 42
TEST_SEED = 456
ANOMALY_SEED = 1005
N_ANOMALIES = 20

# Baseline: flag a reading if ANY single feature is > 3 sd out.
UNIVARIATE_Z_LIMIT = 3.0


class EllipticEnvelopeModel:
    """
    Mahalanobis-distance detector. Included as a reference because
    it models the feature covariance directly - the textbook tool
    for "each value normal, combination abnormal".
    """

    def __init__(self, contamination=0.004):
        self.model = EllipticEnvelope(
            contamination=contamination,
            random_state=RANDOM_SEED,
        )

    def train(self, features):
        self.model.fit(features)

    def predict(self, features):
        return self.model.predict(features)


def univariate_flags(train_df, test_df):
    """1 if any single feature is more than UNIVARIATE_Z_LIMIT sd out."""

    mean = train_df[FEATURES].mean()
    std = train_df[FEATURES].std()
    z = (test_df[FEATURES] - mean) / std

    return (z.abs() > UNIVARIATE_Z_LIMIT).any(axis=1).astype(int).to_numpy()


def _scores(name, y_true, y_pred):
    return {
        "Model": name,
        "Precision": precision_score(y_true, y_pred, zero_division=0),
        "Recall": recall_score(y_true, y_pred, zero_division=0),
        "F1": f1_score(y_true, y_pred, zero_division=0),
        "Caught": int(((y_true == 1) & (y_pred == 1)).sum()),
        "False Alarms": int(((y_true == 0) & (y_pred == 1)).sum()),
    }


def build_datasets():
    """Independent seeds for train and test - no shared rows."""

    train_df = generate_correlated_normal_data(n=5000, seed=TRAIN_SEED)

    test_df = inject_relationship_breaks(
        generate_correlated_normal_data(n=5000, seed=TEST_SEED),
        n_anomalies=N_ANOMALIES,
        seed=ANOMALY_SEED,
    )

    return train_df, test_df


def evaluate_relationship_detection(train_df, test_df):
    """
    Train each detector on normal data only and score it on the
    relationship-break test set.

    The scaler is fit on TRAIN ONLY, then applied to test.
    Without scaling, stock_count (sd 30) dominates LOF's distance
    and the temperature/humidity relationship is invisible.
    """

    y_true = test_df["is_anomaly"].to_numpy()

    scaler = StandardScaler().fit(train_df[FEATURES])
    x_train = scaler.transform(train_df[FEATURES])
    x_test = scaler.transform(test_df[FEATURES])

    candidates = {
        "Isolation Forest": IsolationForestModel(),
        "One-Class SVM": OneClassSVMModel(),
        "LOF": LOFModel(),
        "Elliptic Envelope": EllipticEnvelopeModel(),
    }

    rows = [
        _scores(
            "Univariate z-score (baseline)",
            y_true,
            univariate_flags(train_df, test_df),
        )
    ]

    for name, model in candidates.items():
        model.train(x_train)
        y_pred = (np.asarray(model.predict(x_test)) == -1).astype(int)
        rows.append(_scores(name, y_true, y_pred))

    return pd.DataFrame(rows)


def run():
    np.random.seed(RANDOM_SEED)

    train_df, test_df = build_datasets()
    results = evaluate_relationship_detection(train_df, test_df)

    print(results.to_string(index=False))

    # Imported here so the unit tests don't need an MLflow install.
    import mlflow

    # Same store as ml-services/demand-forecast. The default file
    # store breaks on Windows paths containing spaces.
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("anomaly-detection-m3-multivariate")

    with mlflow.start_run(run_name="relationship-breaks"):
        mlflow.log_params(
            {
                "train_seed": TRAIN_SEED,
                "test_seed": TEST_SEED,
                "anomaly_seed": ANOMALY_SEED,
                "n_anomalies": N_ANOMALIES,
                "features": ",".join(FEATURES),
            }
        )

        for row in results.to_dict("records"):
            key = row["Model"].split(" (")[0].lower().replace(" ", "_")

            for metric in ("Precision", "Recall", "F1"):
                mlflow.log_metric(f"{key}_{metric.lower()}", row[metric])

    return results


if __name__ == "__main__":
    run()