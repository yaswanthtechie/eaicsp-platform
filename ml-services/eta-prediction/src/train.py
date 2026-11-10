import joblib
import numpy as np

from .paths import (
    MODEL_PATH,
    R14_MODEL_PATH,
    R14_CALIBRATION_MODEL_PATH,
)
from .pipeline import (
    create_pipeline,
    create_eta_history_pipeline,
)


# ---------------------------------------------------------
# Prediction interval calibration artifact
# ---------------------------------------------------------
CALIBRATION_MODEL_PATH = (
    MODEL_PATH.parent
    / "eta_prediction_interval.joblib"
)


# ---------------------------------------------------------
# Prediction interval configuration
# ---------------------------------------------------------
PREDICTION_INTERVAL_COVERAGE = 0.80

# Below this many calibration rows the empirical interval is
# noise rather than a calibrated bound. Unit tests train on
# tiny fixtures on purpose, so train_model() stays permissive;
# main.py enables this gate before production artifacts are
# written.
MIN_PRODUCTION_CALIBRATION_ROWS = 100


def check_production_calibration(calibration: dict) -> None:
    """
    Refuse to publish a prediction interval calibrated on too
    little data.

    An 80% empirical quantile taken over a handful of residuals
    is not a calibrated interval, and a model trained on a test
    fixture will happily produce one.

    This check is called inside train_model() before any
    production artifact is written to disk when the production
    gate is enabled.
    """

    calibration_rows = int(
        calibration.get("calibration_rows", 0)
    )

    if calibration_rows < MIN_PRODUCTION_CALIBRATION_ROWS:
        raise ValueError(
            "Prediction interval was calibrated on "
            f"{calibration_rows} rows, which is below the production "
            f"minimum of {MIN_PRODUCTION_CALIBRATION_ROWS}. "
            "This usually means the model was trained on test fixture "
            "data instead of the real dataset. Do not ship this artifact."
        )


def _calibrate_prediction_interval(
    X_train,
    y_train,
    pipeline_factory,
):
    """
    Build time-preserving prediction-interval calibration metadata.

    The latest 20% of the training data is held out for calibration.
    The calibration model is fitted only on the earlier portion, so
    calibration predictions are out-of-sample and chronological.
    """

    calibration_size = max(
        2,
        int(len(X_train) * 0.20),
    )

    calibration_start = len(X_train) - calibration_size

    X_fit = X_train.iloc[:calibration_start].copy()
    y_fit = y_train.iloc[:calibration_start].copy()

    X_calibration = X_train.iloc[calibration_start:].copy()
    y_calibration = y_train.iloc[calibration_start:].copy()

    # ---------------------------------------------------------
    # Train temporary calibration model
    # ---------------------------------------------------------
    calibration_pipeline = pipeline_factory()

    calibration_pipeline.fit(
        X_fit,
        y_fit,
    )

    # ---------------------------------------------------------
    # Generate out-of-sample calibration predictions
    # ---------------------------------------------------------
    calibration_predictions = np.asarray(
        calibration_pipeline.predict(X_calibration),
        dtype=float,
    )

    y_calibration_array = np.asarray(
        y_calibration,
        dtype=float,
    )

    # ---------------------------------------------------------
    # Calculate absolute residuals
    # ---------------------------------------------------------
    absolute_residuals = np.abs(
        y_calibration_array - calibration_predictions
    )

    if not np.isfinite(absolute_residuals).all():
        raise ValueError(
            "Prediction interval calibration produced "
            "non-finite residuals."
        )

    # ---------------------------------------------------------
    # Calculate empirical interval width
    # ---------------------------------------------------------
    interval_width = float(
        np.quantile(
            absolute_residuals,
            PREDICTION_INTERVAL_COVERAGE,
        )
    )

    if not np.isfinite(interval_width):
        raise ValueError(
            "Prediction interval calibration produced "
            "an invalid interval width."
        )

    # ---------------------------------------------------------
    # Store symmetric residual bounds
    # ---------------------------------------------------------
    calibration = {
        "method": "absolute_residual_quantile",
        "coverage": PREDICTION_INTERVAL_COVERAGE,
        "calibration_fraction": 0.20,
        "calibration_rows": len(X_calibration),
        # Provenance: makes it obvious at a glance whether an
        # artifact came from the real dataset or from a test fixture.
        "training_rows": len(X_train),
        "lower_quantile": (
            1.0 - PREDICTION_INTERVAL_COVERAGE
        ),
        "upper_quantile": (
            PREDICTION_INTERVAL_COVERAGE
        ),
        "interval_width": interval_width,
        "residual_lower": -interval_width,
        "residual_upper": interval_width,
    }

    return calibration


def train_model(
    X_train,
    y_train,
    enforce_production_gate: bool = False,
    use_eta_history_features: bool = False,
):
    """
    Train and save the ETA pipeline.

    The model is trained on the complete training dataset.

    An empirical prediction interval is calibrated using
    out-of-sample predictions generated by a time-preserving
    validation split inside the training data.

    The calibration artifact stores symmetric residual bounds:

        residual_lower = -q
        residual_upper = +q

    where q is the configured absolute-residual quantile.

    This allows prediction to construct:

        lower = prediction + residual_lower
        upper = prediction + residual_upper

    When enforce_production_gate=True, the calibration is
    validated before any production artifact is written.
    """

    # ---------------------------------------------------------
    # 1. Validate minimum training size
    # ---------------------------------------------------------
    if len(X_train) != len(y_train):
        raise ValueError(
            "X_train and y_train must contain "
            "the same number of rows."
        )

    if len(X_train) < 4:
        raise ValueError(
            "At least 4 training rows are required "
            "for prediction interval calibration."
        )

    # ---------------------------------------------------------
    # 2. Create the production pipeline
    # ---------------------------------------------------------
    pipeline_factory = (
        create_eta_history_pipeline
        if use_eta_history_features
        else create_pipeline
    )

    pipeline = pipeline_factory()

    # ---------------------------------------------------------
    # 3. Create prediction interval calibration
    # ---------------------------------------------------------
    calibration = _calibrate_prediction_interval(
        X_train,
        y_train,
        pipeline_factory,
    )

    # ---------------------------------------------------------
    # 4. Production gate: BEFORE anything is written to disk
    #
    # A failing production run must never overwrite an existing
    # good production artifact.
    # ---------------------------------------------------------
    if enforce_production_gate:
        check_production_calibration(calibration)

    # ---------------------------------------------------------
    # 5. Train final production model
    #
    # IMPORTANT:
    # The final production model uses ALL training rows.
    # The calibration model above is discarded after the
    # interval width has been calculated.
    # ---------------------------------------------------------
    pipeline.fit(
        X_train,
        y_train,
    )

    # ---------------------------------------------------------
    # 6. Save production model
    # ---------------------------------------------------------
    # Ensure the artifact directory exists — train_model() can
    # be called directly (tests, notebooks, other scripts)
    # without going through main.py's ensure_directories().

    # R14 model is saved separately from the production serving model.
    R14_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    model_path = (
        R14_MODEL_PATH
        if use_eta_history_features
        else MODEL_PATH
    )

    calibration_path = (
        R14_CALIBRATION_MODEL_PATH
        if use_eta_history_features
        else CALIBRATION_MODEL_PATH
    )

    joblib.dump(pipeline, model_path)
    joblib.dump(calibration, calibration_path)

    # ---------------------------------------------------------
    # 7. Return final production pipeline
    # ---------------------------------------------------------
    return pipeline


def train_comparison_model(
    X_train,
    y_train,
    use_eta_history_features: bool = False,
):
    """
    Train an ETA model for comparison only.

    This does not write production artifacts to disk.
    It returns the fitted model and its time-preserving
    prediction-interval calibration metadata.
    """

    if len(X_train) != len(y_train):
        raise ValueError(
            "X_train and y_train must contain "
            "the same number of rows."
        )

    if len(X_train) < 4:
        raise ValueError(
            "At least 4 training rows are required "
            "for prediction interval calibration."
        )

    pipeline_factory = (
        create_eta_history_pipeline
        if use_eta_history_features
        else create_pipeline
    )

    calibration = _calibrate_prediction_interval(
        X_train,
        y_train,
        pipeline_factory,
    )

    model = pipeline_factory()

    model.fit(
        X_train,
        y_train,
    )

    return model, calibration