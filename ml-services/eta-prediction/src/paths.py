from pathlib import Path


# eta-prediction/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Data
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Model artifacts
MODELS_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODELS_DIR / "eta_pipeline.joblib"

R14_MODEL_PATH = MODELS_DIR / "eta_pipeline_r14.joblib"
R14_CALIBRATION_MODEL_PATH = (
    MODELS_DIR / "eta_prediction_interval_r14.joblib"
)

# R15-H2 seed-route model: its own pair, never mixed with the files above
H2_MODEL_PATH = MODELS_DIR / "eta_seed_routes_pipeline.joblib"
H2_CALIBRATION_MODEL_PATH = (
    MODELS_DIR / "eta_seed_routes_interval.joblib"
)

# Committed seed samples (data-platform/seed/samples)
SEED_SAMPLES_DIR = (
    PROJECT_ROOT.parents[1] / "data-platform" / "seed" / "samples"
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