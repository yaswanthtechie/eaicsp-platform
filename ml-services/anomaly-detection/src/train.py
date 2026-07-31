import sys
from pathlib import Path

import joblib
import pandas as pd

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.isolation_forest_model import IsolationForestModel
from src.lof_model import LOFModel
from src.one_class_svm_model import OneClassSVMModel

models_dir = project_root / "models"
models_dir.mkdir(parents=True, exist_ok=True)


def train_models(df: pd.DataFrame):
    """
    Train all anomaly detection models, save them,
    and save a small SHAP background sample.

    Args:
        df: DataFrame containing the sensor data.

    Returns:
        dict: Dictionary containing the trained model wrappers.
    """

    feature_names = ["temperature", "humidity", "stock_count"]
    features = df[feature_names].to_numpy()

    # Save a small background sample for SHAP explainers
    background_sample = (
        df[feature_names]
        .sample(n=min(100, len(df)), random_state=42)
        .reset_index(drop=True)
    )

    background_sample.to_csv(
        models_dir / "background_sample.csv",
        index=False,
    )

    models = {}

    # Isolation Forest
    model1 = IsolationForestModel()
    model1.train(features)

    joblib.dump(
        model1,
        models_dir / "isolation_forest_model.joblib",
    )

    models["iforest"] = model1

    print("Isolation Forest model is trained")
    print("=" * 50)

    # One-Class SVM
    model2 = OneClassSVMModel()
    model2.train(features)

    joblib.dump(
        model2,
        models_dir / "one_class_svm_model.joblib",
    )

    models["ocsvm"] = model2

    print("One-Class SVM model is trained")
    print("=" * 50)

    # Local Outlier Factor
    model3 = LOFModel()
    model3.train(features)

    joblib.dump(
        model3,
        models_dir / "lof_model.joblib",
    )

    models["lof"] = model3

    print("Local Outlier Factor model is trained")
    print("=" * 50)
    print("SHAP background sample saved")

    return models