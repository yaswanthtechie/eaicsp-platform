from pathlib import Path
import sys

import pytest

project_root = Path(__file__).resolve().parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.data import generate_all_datasets
from src.train import train_models, save_models

import pandas as pd

output_dir = project_root / "output"
models_dir = project_root / "models"

@pytest.fixture(scope="session",autouse=True)
def setup_test_environment():
    """
    Preparing all artifacts required by the test suite.

    On a clean clone:
    - generates datasets
    - trains models
    - saves deployed model artifacts

    Existing artifacts are reused.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    # Generate datasets if missing
    
    required_datasets = [
        output_dir / "train_normal.csv",
        output_dir / "test_temperature_spike.csv",
        output_dir / "test_temperature_drift.csv",
        output_dir / "test_combined_anomaly.csv",
        output_dir / "test_stock_anomaly.csv",
    ]

    if not all(path.exists() for path in required_datasets):
        generate_all_datasets()

    # Train models if missing

    required_models = [
        models_dir / "isolation_forest_model.joblib",
        models_dir / "lof_model.joblib",
        models_dir / "one_class_svm_model.joblib",
        models_dir / "background_sample.csv",
    ]

    if not all(path.exists() for path in required_models):
        train_df = pd.read_csv(output_dir / "train_normal.csv")
        models = train_models(train_df)

        # Save trained models
        save_models(models)