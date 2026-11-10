"""
R15-H2 training and evaluation.

Reuses the R14 calibration helper and production gate from train.py,
so there is one calibration implementation, not two.
"""

import joblib
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline

from .features import TARGET_COLUMN
from .h2_features import H2_FEATURES, apply_interval
from .paths import H2_CALIBRATION_MODEL_PATH, H2_MODEL_PATH
from .train import (
    _calibrate_prediction_interval,
    check_production_calibration,
)
from .xg_boost_model import XGBoostModel


def create_h2_pipeline():
    """Passthrough of the H2 features into XGBoost."""

    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", "passthrough", H2_FEATURES),
        ],
        # Keep plain names (distance_km, not numeric__distance_km)
        # so SHAP feature names match what consumers see.
        verbose_feature_names_out=False,
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", XGBoostModel().model),
        ]
    )


def train_h2_model(
    X_train,
    y_train,
    enforce_production_gate: bool = False,
    model_path=H2_MODEL_PATH,
    calibration_path=H2_CALIBRATION_MODEL_PATH,
):
    """
    Calibrate the interval, train on all rows, save the H2 pair.

    X_train must be in chronological order (chronological_split
    returns it sorted), because calibration holds out the latest 20%.
    """

    if len(X_train) != len(y_train):
        raise ValueError(
            "X_train and y_train must contain the same number of rows."
        )

    if len(X_train) < 4:
        raise ValueError(
            "At least 4 training rows are required "
            "for prediction interval calibration."
        )

    X_train = X_train[H2_FEATURES]

    calibration = _calibrate_prediction_interval(
        X_train,
        y_train,
        create_h2_pipeline,
    )

    # Gate BEFORE writing, so a bad run never replaces good files.
    if enforce_production_gate:
        check_production_calibration(calibration)

    pipeline = create_h2_pipeline()
    pipeline.fit(X_train, y_train)

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_path)
    joblib.dump(calibration, calibration_path)

    return pipeline, calibration


def evaluate_h2_model(model, calibration, test):
    """MAE and interval coverage on the chronological test period."""

    y_test = test[TARGET_COLUMN].to_numpy(dtype=float)
    predictions = np.asarray(
        model.predict(test[H2_FEATURES]),
        dtype=float,
    )

    if not np.isfinite(predictions).all():
        raise ValueError("H2 model produced non-finite predictions.")

    low, high = apply_interval(predictions, calibration)

    return {
        "h2_mae": float(mean_absolute_error(y_test, predictions)),
        "h2_interval_coverage": float(
            np.mean((y_test >= low) & (y_test <= high))
        ),
        "h2_nominal_coverage": float(calibration["coverage"]),
    }