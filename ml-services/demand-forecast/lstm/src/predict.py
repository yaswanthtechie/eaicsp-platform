"""
Standalone Prediction Script
------------------------------------------
Loads saved PyTorch weights (.pt file) and scaler to predict a 7-day horizon 
from a 45-day historical input array.
"""

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCALER_PATH = os.path.join(BASE_DIR, "..", "output", "scaler.pkl")

import torch
import numpy as np
from config import LOOKBACK, HORIZON, HIDDEN_SIZE, NUM_LAYERS
from data import load_scaler
from model import MultiStepLSTM


def predict_7_days(historical_data: np.ndarray) -> np.ndarray:
    """
    Loads saved model checkpoint and scaler to forecast 7 days.
    
    Args:
        historical_data: Array of historical daily demand values.
        
    Returns:
        7-day forecasted demand values in original scale.
    """
    device = torch.device("cpu")
    lookback = LOOKBACK
    horizon = HORIZON
    

    assert len(historical_data) == lookback, f"Expected {lookback} days, got {len(historical_data)}"

    # 1. Load Scaler
    scaler = load_scaler(SCALER_PATH)
    scaled_input = scaler.transform(historical_data.reshape(-1, 1)).flatten()

    # 2. Prepare Tensor
    x_tensor = torch.tensor(scaled_input, dtype=torch.float32).view(1, lookback, 1)

    # 3. Load Trained Model Weights (.pt file)
    model = MultiStepLSTM(horizon=horizon, hidden_size=HIDDEN_SIZE, num_layers=NUM_LAYERS)
    model_path = os.path.join(BASE_DIR, "..", "output", "best_model.pt")

    if os.path.exists(model_path):
        model.load_state_dict(torch.load(model_path, map_location=device,weights_only=True))
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
    # Test prediction with historical data
    sample_historical_data = np.random.uniform(100, 150, size=LOOKBACK)
    forecast = predict_7_days(sample_historical_data)

    print("\n" + "="*50)
    print("7-DAY DEMAND FORECAST:")
    print("="*50)
    for day_idx, val in enumerate(forecast, 1):
        print(f" Day +{day_idx}: {val:.2f}")
    print("="*50 + "\n")