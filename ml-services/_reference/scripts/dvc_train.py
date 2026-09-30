from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split


INPUT_PATH = Path("data/reference/processed.csv")
MODEL_PATH = Path("models/dvc_model.pkl")


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Processed dataset not found: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH)

    feature_columns = [
        "sepal_length",
        "sepal_width",
        "petal_length",
        "petal_width",
    ]

    X = df[feature_columns]
    y = df["target"]

    # Deterministic split for reproducibility
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
    )

    model.fit(X_train, y_train)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    print(f"Model written to: {MODEL_PATH}")
    print(f"Training samples: {len(X_train)}")
    print(f"Test samples: {len(X_test)}")


if __name__ == "__main__":
    main()