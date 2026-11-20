import os

# Base directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),".."))

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
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
NUM_LAYERS = 2
DROPOUT = 0.1

# Training Parameters
EPOCHS = 50
BATCH_SIZE = 32
LR = 0.005
N_FOLDS = 3
DATASET_DAYS = 1000

# Uncertainty & Inference Parameters
MC_SAMPLES = 100
CONFIDENCE_LEVEL = 0.90

# ---- Round 12-13: global multi-SKU LSTM ----
GLOBAL_DATA_PATH = "data/global_sku_demand_synthetic.csv"
GLOBAL_SEED = 42
GLOBAL_LOOKBACK = 45
GLOBAL_HORIZON = 7
GLOBAL_BATCH_SIZE = 32
GLOBAL_VALIDATION_BATCH_SIZE = 128
GLOBAL_LEARNING_RATE = 0.001
GLOBAL_EMBEDDING_DIM = 8
GLOBAL_HIDDEN_SIZE = 64
GLOBAL_NUM_LAYERS = 2
GLOBAL_DROPOUT = 0.2
GLOBAL_EPOCHS = 50
GLOBAL_PATIENCE = 8
