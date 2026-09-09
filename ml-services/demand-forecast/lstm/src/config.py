import os

# Base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# File Paths
MODEL_PATH = os.path.join(OUTPUT_DIR, "best_model.pt")
SCALER_PATH = os.path.join(OUTPUT_DIR, "scaler.pkl")
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
EPOCHS = 35
BATCH_SIZE = 32
LR = 0.001

# Uncertainty & Inference Parameters
MC_SAMPLES = 100
CONFIDENCE_LEVEL = 0.90