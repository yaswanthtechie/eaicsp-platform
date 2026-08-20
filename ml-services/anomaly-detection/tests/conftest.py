from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------
# PROJECT PATH
# ---------------------------------------------------------------------

project_root = Path(__file__).resolve().parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# ---------------------------------------------------------------------
# PROJECT IMPORTS
# ---------------------------------------------------------------------

from src.data import generate_all_datasets
from src.model_loader import get_models
from src.train import save_models, train_models


# ---------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------

output_dir = project_root / "output"
models_dir = project_root / "models"


# ---------------------------------------------------------------------
# MODEL CONFIGURATION
# ---------------------------------------------------------------------

MODELS = [
    "iforest",
    "lof",
    "ocsvm",
]

FEATURE_NAMES = [
    "temperature",
    "humidity",
    "stock_count",
]


# ---------------------------------------------------------------------
# TEST ENVIRONMENT
# ---------------------------------------------------------------------

@pytest.fixture(
    scope="session",
    autouse=True,
)
def setup_test_environment():
    """
    Prepare all artifacts required by the test suite.

    On a clean clone:

    1. Generate datasets.
    2. Train models.
    3. Save deployed model artifacts.

    Existing artifacts are reused.
    """

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    models_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -------------------------------------------------------------
    # Required datasets
    # -------------------------------------------------------------

    required_datasets = [
        output_dir / "train_normal.csv",
        output_dir / "calibration_normal.csv",
        output_dir / "test_seasonal_normal.csv",
        output_dir / "test_temperature_spike.csv",
        output_dir / "test_temperature_drift.csv",
        output_dir / "test_combined_anomaly.csv",
        output_dir / "test_stock_anomaly.csv",
    ]

    if not all(
        path.exists()
        for path in required_datasets
    ):
        generate_all_datasets()

    # -------------------------------------------------------------
    # Required model artifacts
    # -------------------------------------------------------------

    required_models = [
        models_dir / "isolation_forest_model.joblib",
        models_dir / "lof_model.joblib",
        models_dir / "one_class_svm_model.joblib",
        models_dir / "background_sample.csv",
    ]

    if not all(
        path.exists()
        for path in required_models
    ):
        train_df = pd.read_csv(
            output_dir / "train_normal.csv"
        )

        trained_models = train_models(
            train_df
        )

        save_models(
            trained_models
        )


# ---------------------------------------------------------------------
# DATASET FIXTURES
# ---------------------------------------------------------------------

@pytest.fixture(scope="session")
def calibration_df(
    setup_test_environment,
):
    """
    Calibration normal dataset.
    """

    path = (
        output_dir
        / "calibration_normal.csv"
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Calibration dataset not found: {path}"
        )

    return pd.read_csv(path)


@pytest.fixture(scope="session")
def seasonal_df(
    setup_test_environment,
):
    """
    Seasonal normal dataset.
    """

    path = (
        output_dir
        / "test_seasonal_normal.csv"
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Seasonal dataset not found: {path}"
        )

    return pd.read_csv(path)


@pytest.fixture(scope="session")
def drift_df(
    setup_test_environment,
):
    """
    Temperature-drift dataset.
    """

    path = (
        output_dir
        / "test_temperature_drift.csv"
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Temperature drift dataset not found: {path}"
        )

    return pd.read_csv(path)


@pytest.fixture(scope="session")
def spike_df(
    setup_test_environment,
):
    """
    Temperature-spike dataset.
    """

    path = (
        output_dir
        / "test_temperature_spike.csv"
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Temperature spike dataset not found: {path}"
        )

    return pd.read_csv(path)


@pytest.fixture(scope="session")
def spikes_df(
    spike_df,
):
    """
    Backward-compatible alias for tests that
    use the plural fixture name.
    """

    return spike_df


# ---------------------------------------------------------------------
# GENERIC DATASETS FIXTURE
# ---------------------------------------------------------------------

@pytest.fixture(scope="session")
def datasets(
    calibration_df,
    seasonal_df,
    drift_df,
):
    """
    Standard dataset tuple used by regime tests.
    """

    return (
        calibration_df,
        seasonal_df,
        drift_df,
    )


# ---------------------------------------------------------------------
# MODEL FIXTURE
# ---------------------------------------------------------------------

@pytest.fixture(
    params=MODELS,
)
def model_name(request):
    """
    Parametrized model fixture.

    Runs once for:

        iforest
        lof
        ocsvm
    """

    return request.param


# ---------------------------------------------------------------------
# MODEL OBJECT FIXTURE
# ---------------------------------------------------------------------

@pytest.fixture
def model(
    model_name,
    setup_test_environment,
):
    """
    Return the trained model corresponding
    to model_name.
    """

    models = get_models()

    if model_name not in models:
        raise ValueError(
            f"Unknown model: {model_name}"
        )

    return models[
        model_name
    ]


# ---------------------------------------------------------------------
# SCORE CALCULATION
# ---------------------------------------------------------------------

def _calculate_scores(
    dataframe,
    model,
):
    """
    Calculate anomaly scores using the
    project's scoring convention.

    model.score(X)
        ->
    anomaly_score = -model.score(X)

    Higher score means more anomalous.
    """

    missing = [
        feature
        for feature in FEATURE_NAMES
        if feature not in dataframe.columns
    ]

    if missing:
        raise ValueError(
            "Dataset is missing required "
            f"features: {missing}"
        )

    X = dataframe[
        FEATURE_NAMES
    ].to_numpy()

    raw_scores = model.score(
        X
    )

    scores = -np.asarray(
        raw_scores,
        dtype=float,
    )

    scores = scores[
        np.isfinite(scores)
    ]

    if scores.size == 0:
        raise ValueError(
            "No finite anomaly scores "
            "were produced."
        )

    return scores


# ---------------------------------------------------------------------
# DEFAULT CALIBRATION SCORES
# ---------------------------------------------------------------------

@pytest.fixture(scope="session")
def calibration_scores(
    calibration_df,
    setup_test_environment,
):
    """
    Calibration scores for the default
    legacy adaptive-engine tests.

    LOF is used because the older tests
    requesting this fixture do not provide
    a model_name fixture.
    """

    models = get_models()

    model = models[
        "lof"
    ]

    return _calculate_scores(
        calibration_df,
        model,
    )


# ---------------------------------------------------------------------
# MODEL-SPECIFIC CALIBRATION SCORES
# ---------------------------------------------------------------------

@pytest.fixture
def model_calibration_scores(
    model_name,
    calibration_df,
    setup_test_environment,
):
    """
    Calibration scores for the selected model.
    """

    models = get_models()

    model = models[
        model_name
    ]

    return _calculate_scores(
        calibration_df,
        model,
    )


# ---------------------------------------------------------------------
# MODEL-SPECIFIC SEASONAL SCORES
# ---------------------------------------------------------------------

@pytest.fixture
def seasonal_scores(
    model_name,
    seasonal_df,
    setup_test_environment,
):
    """
    Seasonal scores for the selected model.
    """

    models = get_models()

    model = models[
        model_name
    ]

    return _calculate_scores(
        seasonal_df,
        model,
    )


# ---------------------------------------------------------------------
# MODEL-SPECIFIC DRIFT SCORES
# ---------------------------------------------------------------------

@pytest.fixture
def drift_scores(
    model_name,
    drift_df,
    setup_test_environment,
):
    """
    Temperature-drift scores for the selected model.
    """

    models = get_models()

    model = models[
        model_name
    ]

    return _calculate_scores(
        drift_df,
        model,
    )


# ---------------------------------------------------------------------
# MODEL-SPECIFIC SPIKE SCORES
# ---------------------------------------------------------------------

@pytest.fixture
def spike_scores(
    model_name,
    spike_df,
    setup_test_environment,
):
    """
    Temperature-spike scores for the selected model.
    """

    models = get_models()

    model = models[
        model_name
    ]

    return _calculate_scores(
        spike_df,
        model,
    )


# ---------------------------------------------------------------------
# ALL MODEL CALIBRATION SCORES
# ---------------------------------------------------------------------

@pytest.fixture(scope="session")
def all_calibration_scores(
    calibration_df,
    setup_test_environment,
):
    """
    Calibration scores for all supported models.
    """

    models = get_models()

    return {
        name: _calculate_scores(
            calibration_df,
            model,
        )
        for name, model in models.items()
        if name in MODELS
    }


# ---------------------------------------------------------------------
# ALL MODEL SEASONAL SCORES
# ---------------------------------------------------------------------

@pytest.fixture(scope="session")
def all_seasonal_scores(
    seasonal_df,
    setup_test_environment,
):
    """
    Seasonal scores for all supported models.
    """

    models = get_models()

    return {
        name: _calculate_scores(
            seasonal_df,
            model,
        )
        for name, model in models.items()
        if name in MODELS
    }