import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split


DATA_PATH = Path("data/reference/processed.csv")
MODEL_PATH = Path("models/dvc_model.pkl")
METRICS_PATH = Path("metrics.json")


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    df = pd.read_csv(DATA_PATH)

    feature_columns = [
        "sepal_length",
        "sepal_width",
        "petal_length",
        "petal_width",
    ]

    X = df[feature_columns]
    y = df["target"]

    # Use exactly the same deterministic split as the training stage.
    _, X_test, _, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    model = joblib.load(MODEL_PATH)

    predictions = model.predict(X_test)

    accuracy = float(accuracy_score(y_test, predictions))

    metrics = {
        "accuracy": accuracy,
        "test_samples": len(y_test),
    }

    METRICS_PATH.write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()