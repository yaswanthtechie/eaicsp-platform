from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------
# PROJECT PATH
# ---------------------------------------------------------------------

project_root = (
    Path(__file__).resolve().parent.parent
)

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
# REQUIRED DATASETS
# ---------------------------------------------------------------------

REQUIRED_DATASETS = [
    "train_normal.csv",
    "calibration_normal.csv",
    "test_seasonal_normal.csv",
    "test_temperature_spike.csv",
    "test_temperature_drift.csv",
    "test_stock_anomaly.csv",
    "test_combined_anomaly.csv",
]


# ---------------------------------------------------------------------
# REQUIRED MODEL ARTIFACTS
# ---------------------------------------------------------------------

REQUIRED_MODEL_ARTIFACTS = [
    "isolation_forest_model.joblib",
    "lof_model.joblib",
    "one_class_svm_model.joblib",
    "background_sample.csv",
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

    This fixture is intentionally self-contained so that a fresh
    clone can run the test suite without requiring manually generated
    datasets or manually trained model artifacts.

    Steps:

        1. Create output/models directories.
        2. Check required datasets.
        3. Generate datasets if any are missing.
        4. Check required model artifacts.
        5. Train and save models if any artifacts are missing.

    Existing complete artifacts are reused.
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
    # DATASET CHECK
    # -------------------------------------------------------------

    dataset_paths = [
        output_dir / filename
        for filename in REQUIRED_DATASETS
    ]

    datasets_ready = all(
        path.is_file()
        for path in dataset_paths
    )

    if not datasets_ready:

        print(
            "\n"
            "============================================================\n"
            "TEST SETUP: GENERATING DATASETS\n"
            "============================================================"
        )

        generate_all_datasets()

    # -------------------------------------------------------------
    # VERIFY DATASETS AFTER GENERATION
    # -------------------------------------------------------------

    missing_datasets = [
        path
        for path in dataset_paths
        if not path.is_file()
    ]

    if missing_datasets:

        missing_names = [
            path.name
            for path in missing_datasets
        ]

        raise FileNotFoundError(
            "Dataset generation completed, but "
            "the following required datasets are "
            f"still missing: {missing_names}"
        )

    # -------------------------------------------------------------
    # MODEL ARTIFACT CHECK
    # -------------------------------------------------------------

    model_paths = [
        models_dir / filename
        for filename in REQUIRED_MODEL_ARTIFACTS
    ]

    models_ready = all(
        path.is_file()
        for path in model_paths
    )

    if not models_ready:

        print(
            "\n"
            "============================================================\n"
            "TEST SETUP: TRAINING MODELS\n"
            "============================================================"
        )

        train_path = (
            output_dir
            / "train_normal.csv"
        )

        if not train_path.is_file():

            raise FileNotFoundError(
                "Training dataset is missing: "
                f"{train_path}"
            )

        train_df = pd.read_csv(
            train_path
        )

        trained_models = train_models(
            train_df
        )

        save_models(
            trained_models
        )

    # -------------------------------------------------------------
    # VERIFY MODEL ARTIFACTS AFTER TRAINING
    # -------------------------------------------------------------

    missing_models = [
        path
        for path in model_paths
        if not path.is_file()
    ]

    if missing_models:

        missing_names = [
            path.name
            for path in missing_models
        ]

        raise FileNotFoundError(
            "Model training completed, but "
            "the following required artifacts "
            f"are still missing: {missing_names}"
        )


# ---------------------------------------------------------------------
# DATASET LOADING HELPER
# ---------------------------------------------------------------------

def _load_dataset(
    filename,
):
    """
    Load a generated dataset and verify that
    all required ML features exist.
    """

    path = (
        output_dir
        / filename
    )

    if not path.is_file():

        raise FileNotFoundError(
            f"Dataset not found: {path}"
        )

    dataframe = pd.read_csv(
        path
    )

    missing = [
        feature
        for feature in FEATURE_NAMES
        if feature not in dataframe.columns
    ]

    if missing:

        raise ValueError(
            f"{filename} is missing required "
            f"features: {missing}"
        )

    return dataframe


# ---------------------------------------------------------------------
# DATASET FIXTURES
# ---------------------------------------------------------------------

@pytest.fixture(
    scope="session",
)
def train_df(
    setup_test_environment,
):
    """
    Normal training dataset.
    """

    return _load_dataset(
        "train_normal.csv"
    )


@pytest.fixture(
    scope="session",
)
def calibration_df(
    setup_test_environment,
):
    """
    Normal calibration dataset.
    """

    return _load_dataset(
        "calibration_normal.csv"
    )


@pytest.fixture(
    scope="session",
)
def seasonal_df(
    setup_test_environment,
):
    """
    Seasonal normal dataset.
    """

    return _load_dataset(
        "test_seasonal_normal.csv"
    )


@pytest.fixture(
    scope="session",
)
def drift_df(
    setup_test_environment,
):
    """
    Temperature-drift dataset.
    """

    return _load_dataset(
        "test_temperature_drift.csv"
    )


@pytest.fixture(
    scope="session",
)
def spike_df(
    setup_test_environment,
):
    """
    Temperature-spike dataset.
    """

    return _load_dataset(
        "test_temperature_spike.csv"
    )


@pytest.fixture(
    scope="session",
)
def stock_df(
    setup_test_environment,
):
    """
    Stock anomaly dataset.
    """

    return _load_dataset(
        "test_stock_anomaly.csv"
    )


@pytest.fixture(
    scope="session",
)
def combined_df(
    setup_test_environment,
):
    """
    Combined anomaly dataset.
    """

    return _load_dataset(
        "test_combined_anomaly.csv"
    )


@pytest.fixture(
    scope="session",
)
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

@pytest.fixture(
    scope="session",
)
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
def model_name(
    request,
):
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
# MODEL COLLECTION FIXTURE
# ---------------------------------------------------------------------

@pytest.fixture(
    scope="session",
)
def models(
    setup_test_environment,
):
    """
    Return all deployed models.
    """

    loaded_models = get_models()

    missing = [
        model_name
        for model_name in MODELS
        if model_name not in loaded_models
    ]

    if missing:

        raise ValueError(
            "Required models are missing "
            f"from model_loader: {missing}"
        )

    return {
        model_name: loaded_models[
            model_name
        ]
        for model_name in MODELS
    }


# ---------------------------------------------------------------------
# SCORE CALCULATION
# ---------------------------------------------------------------------

def _calculate_scores(
    dataframe,
    model,
):
    """
    Calculate anomaly scores using the project's
    canonical scoring convention.

    IMPORTANT:

        model.score(X)
            =
        project anomaly score

    Therefore:

        higher score = more anomalous

    Do NOT negate model.score(X) here.

    This must remain consistent with:

        predict.py
        adaptive_threshold.py
        cost_threshold_tuning.py
        orchestration.py
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

    scores = model.score(
        X
    )

    scores = np.asarray(
        scores,
        dtype=float,
    )

    if scores.ndim != 1:

        scores = scores.reshape(
            -1
        )

    if len(scores) != len(
        dataframe
    ):

        raise ValueError(
            "Number of anomaly scores "
            "does not match dataset size: "
            f"{len(scores)} scores for "
            f"{len(dataframe)} rows."
        )

    if scores.size == 0:

        raise ValueError(
            "No anomaly scores were produced."
        )

    if not np.all(
        np.isfinite(scores)
    ):

        raise ValueError(
            "Non-finite anomaly scores "
            "were produced."
        )

    return scores


# ---------------------------------------------------------------------
# DEFAULT CALIBRATION SCORES
# ---------------------------------------------------------------------

@pytest.fixture(
    scope="session",
)
def calibration_scores(
    calibration_df,
    setup_test_environment,
):
    """
    Calibration scores for legacy adaptive-engine tests.

    LOF is used because older tests requesting this fixture
    may not provide model_name.

    New model-aware tests should prefer:

        model_calibration_scores
    """

    models = get_models()

    if "lof" not in models:

        raise ValueError(
            "LOF model is required for "
            "the legacy calibration_scores fixture."
        )

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
# MODEL-SPECIFIC STOCK SCORES
# ---------------------------------------------------------------------

@pytest.fixture
def stock_scores(
    model_name,
    stock_df,
    setup_test_environment,
):
    """
    Stock-anomaly scores for the selected model.
    """

    models = get_models()

    model = models[
        model_name
    ]

    return _calculate_scores(
        stock_df,
        model,
    )


# ---------------------------------------------------------------------
# MODEL-SPECIFIC COMBINED SCORES
# ---------------------------------------------------------------------

@pytest.fixture
def combined_scores(
    model_name,
    combined_df,
    setup_test_environment,
):
    """
    Combined-anomaly scores for the selected model.
    """

    models = get_models()

    model = models[
        model_name
    ]

    return _calculate_scores(
        combined_df,
        model,
    )


# ---------------------------------------------------------------------
# ALL MODEL CALIBRATION SCORES
# ---------------------------------------------------------------------

@pytest.fixture(
    scope="session",
)
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

@pytest.fixture(
    scope="session",
)
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


# ---------------------------------------------------------------------
# ALL MODEL DRIFT SCORES
# ---------------------------------------------------------------------

@pytest.fixture(
    scope="session",
)
def all_drift_scores(
    drift_df,
    setup_test_environment,
):
    """
    Temperature-drift scores for all supported models.
    """

    models = get_models()

    return {
        name: _calculate_scores(
            drift_df,
            model,
        )
        for name, model in models.items()
        if name in MODELS
    }


# ---------------------------------------------------------------------
# ALL MODEL SPIKE SCORES
# ---------------------------------------------------------------------

@pytest.fixture(
    scope="session",
)
def all_spike_scores(
    spike_df,
    setup_test_environment,
):
    """
    Temperature-spike scores for all supported models.
    """

    models = get_models()

    return {
        name: _calculate_scores(
            spike_df,
            model,
        )
        for name, model in models.items()
        if name in MODELS
    }


# ---------------------------------------------------------------------
# ALL MODEL STOCK SCORES
# ---------------------------------------------------------------------

@pytest.fixture(
    scope="session",
)
def all_stock_scores(
    stock_df,
    setup_test_environment,
):
    """
    Stock-anomaly scores for all supported models.
    """

    models = get_models()

    return {
        name: _calculate_scores(
            stock_df,
            model,
        )
        for name, model in models.items()
        if name in MODELS
    }


# ---------------------------------------------------------------------
# ALL MODEL COMBINED SCORES
# ---------------------------------------------------------------------

@pytest.fixture(
    scope="session",
)
def all_combined_scores(
    combined_df,
    setup_test_environment,
):
    """
    Combined-anomaly scores for all supported models.
    """

    models = get_models()

    return {
        name: _calculate_scores(
            combined_df,
            model,
        )
        for name, model in models.items()
        if name in MODELS
    }