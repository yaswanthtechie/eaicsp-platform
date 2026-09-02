import os

# Base directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# File Paths
MODEL_PATH = os.path.join(OUTPUT_DIR, "best_model.pt")
SCALER_PATH = os.path.join(OUTPUT_DIR, "scaler.pkl")
ONNX_PATH = os.path.join(OUTPUT_DIR, "best_model.onnx")
LOSS_CURVE_PATH = os.path.join(OUTPUT_DIR, "loss_curve.png")

# Reproducibility
RANDOM_SEED = 42

# Winning Model Hyperparameters
LOOKBACK = 45
HORIZON = 7
HIDDEN_SIZE = 32
NUM_LAYERS = 1
DROPOUT = 0.2

# Training Parameters
EPOCHS = 50
BATCH_SIZE = 32
LR = 0.001
N_FOLDS = 3
DATASET_DAYS = 1000

# Uncertainty & Inference Parameters
MC_SAMPLES = 100
CONFIDENCE_LEVEL = 0.90