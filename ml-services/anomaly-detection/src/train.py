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


def save_background_sample(df: pd.DataFrame):
    """
    Save a small background sample used by SHAP explainers.
    """

    feature_names = [
        "temperature",
        "humidity",
        "stock_count",
    ]

    background_sample = (
        df[feature_names]
        .sample(
            n=min(100, len(df)),
            random_state=42,
        )
        .reset_index(drop=True)
    )

    background_sample.to_csv(
        models_dir / "background_sample.csv",
        index=False,
    )


def train_models(df: pd.DataFrame):
    """
    Train all anomaly detection models.

    Models are returned but NOT saved.
    Saving is handled separately by save_models().

    Parameters
    ----------
    df : pandas.DataFrame
        Normal training data.

    Returns
    -------
    dict
        Dictionary of trained models.
    """

    feature_names = [
        "temperature",
        "humidity",
        "stock_count",
    ]

    features = df[feature_names].to_numpy()

    save_background_sample(df)

    models = {}

    # Isolation Forest
    model = IsolationForestModel()
    model.train(features)

    models["iforest"] = model

    print("Isolation Forest trained")

    # One-Class SVM
    model = OneClassSVMModel()
    model.train(features)

    models["ocsvm"] = model

    print("One-Class SVM trained")

    # Local Outlier Factor
    model = LOFModel()
    model.train(features)

    models["lof"] = model

    print("Local Outlier Factor trained")

    print("=" * 50)

    return models


def save_models(models):
    """
    Deploy trained models by saving them to disk.

    Parameters
    ----------
    models : dict
        Dictionary returned by train_models().
    """

    joblib.dump(
        models["iforest"],
        models_dir / "isolation_forest_model.joblib",
    )

    joblib.dump(
        models["ocsvm"],
        models_dir / "one_class_svm_model.joblib",
    )

    joblib.dump(
        models["lof"],
        models_dir / "lof_model.joblib",
    )

    print("Models deployed successfully.")
    print("SHAP background sample saved.")
    print("=" * 50)