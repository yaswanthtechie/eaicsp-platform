"""
Standalone Prediction Script
------------------------------------------
Loads saved PyTorch weights (.pt file) and scaler to predict a 7-day horizon 
from a 30-day historical input array.
"""

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCALER_PATH = os.path.join(BASE_DIR, "..", "output", "scaler.pkl")

import torch
import numpy as np
from data import load_scaler
from model import MultiStepLSTM


def predict_7_days(historical_30_days: np.ndarray) -> np.ndarray:
    """
    Loads saved model checkpoint and scaler to forecast 7 days.
    
    Args:
        historical_30_days: Array of 30 historical daily demand values.
        
    Returns:
        7-day forecasted demand values in original scale.
    """
    device = torch.device("cpu")
    lookback = 30
    horizon = 7

    assert len(historical_30_days) == lookback, f"Expected {lookback} days, got {len(historical_30_days)}"

    # 1. Load Scaler
    scaler = load_scaler(SCALER_PATH)
    scaled_input = scaler.transform(historical_30_days.reshape(-1, 1)).flatten()

    # 2. Prepare Tensor
    x_tensor = torch.tensor(scaled_input, dtype=torch.float32).view(1, lookback, 1)

    # 3. Load Trained Model Weights (.pt file)
    model = MultiStepLSTM(horizon=horizon)
    model_path = os.path.join(BASE_DIR, "..", "output", "best_model.pt")

    if os.path.exists(model_path):
        model.load_state_dict(torch.load(model_path, map_location=device))
        print(f"Loaded model weights from {model_path}")
    else:
        raise FileNotFoundError(f"Model file not found at {model_path}. Run train.py first!")

    # 4. Perform Inference
    model.eval()
    with torch.no_grad():
        scaled_preds = model(x_tensor).numpy()

    # 5. Inverse Transform to Original Scale
    unscaled_preds = scaler.inverse_transform(scaled_preds.reshape(-1, 1)).flatten()
    return unscaled_preds


if __name__ == "__main__":
    # Test prediction with 30 dummy days
    sample_30_days = np.random.uniform(100, 150, size=30)
    forecast = predict_7_days(sample_30_days)
    
    print("\n" + "="*50)
    print("7-DAY DEMAND FORECAST:")
    print("="*50)
    for day_idx, val in enumerate(forecast, 1):
        print(f" Day +{day_idx}: {val:.2f}")
    print("="*50 + "\n")