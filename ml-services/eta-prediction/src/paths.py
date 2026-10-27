from pathlib import Path


# eta-prediction/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Data
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Model artifacts
MODELS_DIR = PROJECT_ROOT / "models"

# R14
MODEL_PATH = MODELS_DIR / "eta_pipeline.joblib"

# R15-H2 seed-route model
H2_MODEL_PATH = (
    MODELS_DIR / "eta_seed_routes_pipeline.joblib"
)

H2_CALIBRATION_MODEL_PATH = (
    MODELS_DIR / "eta_seed_routes_interval.joblib"
)

# MLflow
MLFLOW_DIR = PROJECT_ROOT / "mlruns"


def ensure_directories() -> None:
    """Create project directories if they do not already exist."""
    for directory in (
        RAW_DATA_DIR,
        PROCESSED_DATA_DIR,
        MODELS_DIR,
        MLFLOW_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)