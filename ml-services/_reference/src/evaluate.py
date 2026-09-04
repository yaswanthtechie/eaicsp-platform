"""
Model evaluation utilities.

This module evaluates a trained classification model using
common classification metrics.

Metrics:
- Accuracy
- Precision (Weighted)
- Recall (Weighted)
- F1 Score (Weighted)
"""

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)


def evaluate(model, X_test, y_test):
    """
    Evaluate a trained classification model.

    Returns
    -------
    tuple
        (
            accuracy,
            precision,
            recall,
            f1,
        )
    """

    predictions = model.predict(X_test)

    accuracy = accuracy_score(
        y_test,
        predictions,
    )

    precision = precision_score(
        y_test,
        predictions,
        average="weighted",
        zero_division=0,
    )

    recall = recall_score(
        y_test,
        predictions,
        average="weighted",
        zero_division=0,
    )

    f1 = f1_score(
        y_test,
        predictions,
        average="weighted",
        zero_division=0,
    )

    return (
        accuracy,
        precision,
        recall,
        f1,
    )