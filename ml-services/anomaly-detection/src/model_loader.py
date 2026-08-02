from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd
import shap

project_root = Path(__file__).resolve().parent.parent
models_dir = project_root / "models"

feature_names = [
    "temperature",
    "humidity",
    "stock_count",
]


def get_model_metadata():
    """
    Read model deployment metadata.
    Creates the metadata file if it does not exist.
    """

    metadata_path = models_dir / "model_metadata.json"

    if not metadata_path.exists():

        metadata = {
            "model_version": "1.0.0",
            "last_retrained": None,
        }

        with open(metadata_path, "w") as file:
            json.dump(metadata, file, indent=4)

        return metadata

    with open(metadata_path, "r") as file:
        return json.load(file)


def get_model_version():
    """
    Return the latest deployed model version.
    """

    return get_model_metadata()["model_version"]


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

            masker = shap.maskers.Independent(
                get_background()
            )

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