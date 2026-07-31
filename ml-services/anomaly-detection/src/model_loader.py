from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap

project_root = Path(__file__).resolve().parent.parent
models_dir = project_root / "models"

MODEL_VERSION = "1.0.0"

feature_names = ["temperature", "humidity", "stock_count"]


def make_prediction(model):

    def predict_with_feature_names(values):
        if isinstance(values, pd.DataFrame):
            model_input = values[feature_names].to_numpy()
        else:
            model_input = np.asarray(values)

        return model.score(model_input)

    return predict_with_feature_names


_models = None
_background = None
masker = None
explainers = {}


def get_models():
    global _models

    if _models is None:
        model_paths = {
            "iforest": models_dir / "isolation_forest_model.joblib",
            "lof": models_dir / "lof_model.joblib",
            "ocsvm": models_dir / "one_class_svm_model.joblib",
        }

        missing = [
            str(path.name)
            for path in model_paths.values()
            if not path.exists()
        ]

        if missing:
            raise FileNotFoundError(
                "Model artifacts not found. "
                "Run 'python main.py' to generate the trained models."
            )

        _models = {
            name: joblib.load(path)
            for name, path in model_paths.items()
        }

    return _models


def get_background():
    global _background

    if _background is None:
        background_path = models_dir / "background_sample.csv"

        if not background_path.exists():
            raise FileNotFoundError(
                "background_sample.csv not found. "
                "Run 'python main.py' to generate the required artifacts."
            )

        _background = pd.read_csv(background_path).to_numpy()

    return _background


def get_explainer(model_name):
    global masker

    if model_name not in explainers:

        if masker is None:
            masker = shap.maskers.Independent(get_background())

        model = get_models()[model_name]

        try:
            explainers[model_name] = shap.Explainer(
                make_prediction(model),
                masker,
                feature_names=feature_names,
            )
        except Exception:
            explainers[model_name] = None

    return explainers[model_name]