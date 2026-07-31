import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import precision_score, recall_score

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

models_dir = project_root / "models"


def evaluate_model(model_path, model_name, features, y_true):
    model = joblib.load(model_path)

    y_pred = (model.predict(features) == -1).astype(int)

    return {
        "Model": model_name,
        "Precision": precision_score(y_true, y_pred),
        "Recall": recall_score(y_true, y_pred),
        "Caught": ((y_true == 1) & (y_pred == 1)).sum(),
        "False Alarms": ((y_true == 0) & (y_pred == 1)).sum(),
        "Predicted": y_pred.sum(),
    }


def evaluate_models(df: pd.DataFrame):
    """
    Evaluate all trained anomaly detection models.
    """

    features = df[
        ["temperature", "humidity", "stock_count"]
    ].to_numpy()

    y_true = df["is_anomaly"]

    results = [
        evaluate_model(
            models_dir / "isolation_forest_model.joblib",
            "Isolation Forest",
            features,
            y_true,
        ),
        evaluate_model(
            models_dir / "one_class_svm_model.joblib",
            "One-Class SVM",
            features,
            y_true,
        ),
        evaluate_model(
            models_dir / "lof_model.joblib",
            "Local Outlier Factor",
            features,
            y_true,
        ),
    ]

    results_df = pd.DataFrame(results)

    print(results_df)


    return results_df