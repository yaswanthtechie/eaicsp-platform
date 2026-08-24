import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
MODEL_PATH = os.path.join(OUTPUT_DIR, "best_model.pt")
SCALER_PATH = os.path.join(OUTPUT_DIR, "scaler.pkl")
LOSS_CURVE_PATH = os.path.join(OUTPUT_DIR, "loss_curve.png")

# Best sweep configuration (h64_l2_lb45)
LOOKBACK = 45
HIDDEN_SIZE = 64
NUM_LAYERS = 2
HORIZON = 7
EPOCHS = 25
DROPOUT = 0.2
MC_SAMPLES = 100
CONFIDENCE_LEVEL = 0.90
RANDOM_SEED = 42