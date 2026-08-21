from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd
import shap

from .adaptive_threshold import (
    get_adaptive_threshold,
)


project_root = Path(__file__).resolve().parent.parent
models_dir = project_root / "models"
output_dir = project_root / "output"

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

            model_input = values[
                feature_names
            ].to_numpy()

        else:

            model_input = np.asarray(values)

        return model.score(
            model_input
        )

    return predict_with_feature_names


_models = None
_background = None
masker = None
explainers = {}

_adaptive_thresholds_initialized = False


def get_models():

    global _models

    if _models is None:

        model_paths = {
            "iforest": (
                models_dir
                / "isolation_forest_model.joblib"
            ),
            "lof": (
                models_dir
                / "lof_model.joblib"
            ),
            "ocsvm": (
                models_dir
                / "one_class_svm_model.joblib"
            ),
        }

        missing = [
            str(path.name)
            for path in model_paths.values()
            if not path.exists()
        ]

        if missing:

            raise FileNotFoundError(
                "Model artifacts not found. "
                "Run 'python main.py' to generate "
                "the trained models."
            )

        _models = {
            name: joblib.load(path)
            for name, path in model_paths.items()
        }

    return _models


def get_background():

    global _background

    if _background is None:

        background_path = (
            models_dir
            / "background_sample.csv"
        )

        if not background_path.exists():

            raise FileNotFoundError(
                "background_sample.csv not found. "
                "Run 'python main.py' to generate "
                "the required artifacts."
            )

        _background = pd.read_csv(
            background_path
        ).to_numpy()

    return _background


def get_explainer(model_name):

    global masker

    if model_name not in explainers:

        if masker is None:

            masker = shap.maskers.Independent(
                get_background()
            )

        model = get_models()[
            model_name
        ]

        try:

            explainers[model_name] = (
                shap.Explainer(
                    make_prediction(model),
                    masker,
                    feature_names=feature_names,
                )
            )

        except Exception:

            explainers[model_name] = None

    return explainers[model_name]


# ------------------------------------------------------------
# Adaptive Threshold Calibration
# ------------------------------------------------------------

def initialize_adaptive_thresholds():
    """
    Initialize model-specific adaptive thresholds
    using the deployed models and calibration_normal.csv.

    The calibration dataset must contain normal readings
    for the following features:

        temperature
        humidity
        stock_count

    Each model's anomaly score follows the project convention:

        anomaly_score = -model.score(...)

    Therefore:

        higher score = more anomalous

    The AdaptiveThreshold manager is initialized with
    the complete calibration score distribution.

    The manager itself uses its configured percentile
    to calculate the initial threshold.
    """

    global _adaptive_thresholds_initialized

    if _adaptive_thresholds_initialized:

        return

    calibration_path = (
        output_dir
        / "calibration_normal.csv"
    )

    if not calibration_path.exists():

        raise FileNotFoundError(
            "calibration_normal.csv not found. "
            "Run the calibration data generation step "
            "before using adaptive prediction."
        )

    calibration_df = pd.read_csv(
        calibration_path
    )

    missing_columns = [
        column
        for column in feature_names
        if column not in calibration_df.columns
    ]

    if missing_columns:

        raise ValueError(
            "Calibration dataset is missing "
            "required feature columns: "
            f"{missing_columns}"
        )

    if calibration_df.empty:

        raise ValueError(
            "calibration_normal.csv contains "
            "no calibration samples."
        )

    X_calibration = (
        calibration_df[
            feature_names
        ].to_numpy()
    )

    models = get_models()

    for model_name, model in models.items():

        raw_scores = model.score(
            X_calibration
        )

        # Project convention:
        #
        # Higher score = more anomalous.
        #
        anomaly_scores = -np.asarray(
            raw_scores,
            dtype=float,
        )

        manager = get_adaptive_threshold(
            model_name
        )

        manager.initialize(
            anomaly_scores
        )

    _adaptive_thresholds_initialized = True


def reset_adaptive_threshold_initialization():
    """
    Reset the application-level adaptive calibration flag.

    This does NOT clear the threshold managers themselves.

    Primarily useful for tests where the adaptive managers
    are reset separately.
    """

    global _adaptive_thresholds_initialized

    _adaptive_thresholds_initialized = False