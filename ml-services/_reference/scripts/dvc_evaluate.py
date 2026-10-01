"""
DVC evaluate stage: score the served model on the training split's test set.
"""

import json
from pathlib import Path

import joblib
from sklearn.metrics import accuracy_score

from src.data import (
    PROJECT_ROOT,
    load_data,
)


MODEL_PATH = (
    PROJECT_ROOT
    / "models"
    / "model.pkl"
)

METRICS_PATH = (
    PROJECT_ROOT
    / "metrics.json"
)


def main():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found: {MODEL_PATH}"
        )

    # Exactly the same data and split as src.train.
    _, X_test, _, y_test = load_data()

    model = joblib.load(
        MODEL_PATH
    )

    metrics = {
        "accuracy": float(
            accuracy_score(
                y_test,
                model.predict(X_test),
            )
        ),
        "test_samples": int(
            len(y_test)
        ),
    }

    METRICS_PATH.write_text(
        json.dumps(
            metrics,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            metrics,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()