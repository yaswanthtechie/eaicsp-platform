"""
Inference Pipeline with ONNX/PyTorch Backend, MC-Dropout Bounds & Robustness Sanitization
"""

import os
import pickle
import numpy as np
import onnxruntime as ort
import torch

from config import (
    DROPOUT,
    HIDDEN_SIZE,
    HORIZON,
    LOOKBACK,
    MODEL_PATH,
    NUM_LAYERS,
    ONNX_PATH,
    RANDOM_SEED,
    SCALER_PATH,
)
from model import MultiStepLSTM


def sanitize_input_sequence(sequence: list, expected_len: int = LOOKBACK) -> np.ndarray:
    """Sanitizes adversarial inputs (handles NaNs, infs, negative demand, and extreme outlier spikes)."""
    if len(sequence) != expected_len:
        raise ValueError(f"Expected sequence length {expected_len}, got {len(sequence)}")

    arr = np.array(sequence, dtype=np.float32)

    # 1. Handle NaNs and Infinite values via linear interpolation
    if np.isnan(arr).any() or np.isinf(arr).any():
        nans = np.isnan(arr) | np.isinf(arr)
        x = lambda z: z.nonzero()[0]
        if nans.all():
            arr = np.zeros_like(arr)
        else:
            arr[nans] = np.interp(x(nans), x(~nans), arr[~nans])

    # 2. Lower bound guard: non-negative demand
    arr = np.clip(arr, a_min=0.0, a_max=None)

    # 3. Outlier winsorization (caps extreme 10000x spikes exceeding 10x median non-zero baseline)
    median_val = np.median(arr[arr > 0]) if np.any(arr > 0) else 100.0
    cap_threshold = max(median_val * 10.0, 5000.0)
    arr = np.clip(arr, a_min=0.0, a_max=cap_threshold)

    return arr


def compute_mc_dropout_bounds(
    model: torch.nn.Module,
    scaled_seq: np.ndarray,
    scaler,
    n_iterations: int = 50,
) -> tuple:
    """Computes empirical 90% confidence intervals via Monte Carlo Dropout."""
    if hasattr(model, "enable_mc_dropout"):
        model.enable_mc_dropout()
    else:
        model.train()

    x_tensor = torch.tensor(scaled_seq, dtype=torch.float32)

    stochastic_preds = []
    with torch.no_grad():
        for _ in range(n_iterations):
            pred_scaled = model(x_tensor).numpy()
            pred_inv = scaler.inverse_transform(pred_scaled.reshape(-1, 1)).reshape(pred_scaled.shape)
            stochastic_preds.append(pred_inv.flatten())

    stochastic_preds = np.array(stochastic_preds)  # shape: (n_iterations, horizon)
    lower_90 = np.percentile(stochastic_preds, 5, axis=0)
    upper_90 = np.percentile(stochastic_preds, 95, axis=0)

    lower_bound = [max(0.0, round(float(val), 2)) for val in lower_90]
    upper_bound = [max(0.0, round(float(val), 2)) for val in upper_90]
    return lower_bound, upper_bound


def forecast_demand(historical_demand: list, use_onnx: bool = True, mc_iterations: int = 50) -> dict:
    """Runs demand forecast with calibrated empirical confidence bounds."""
    clean_seq = sanitize_input_sequence(historical_demand, expected_len=LOOKBACK)

    if not os.path.exists(SCALER_PATH):
        raise FileNotFoundError(f"Scaler not found at '{SCALER_PATH}'. Run src/train.py first.")

    with open(SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)

    scaled_seq = scaler.transform(clean_seq.reshape(-1, 1)).reshape(1, LOOKBACK, 1).astype(np.float32)

    # 1. Primary deterministic point forecast
    if use_onnx and os.path.exists(ONNX_PATH):
        so = ort.SessionOptions()
        so.log_severity_level = 3
        session = ort.InferenceSession(ONNX_PATH, sess_options=so, providers=["CPUExecutionProvider"])
        inputs = {session.get_inputs()[0].name: scaled_seq}
        scaled_pred = session.run(None, inputs)[0]
    else:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Model checkpoint not found at '{MODEL_PATH}'. Run src/train.py first.")
        model = MultiStepLSTM(
            input_size=1,
            hidden_size=HIDDEN_SIZE,
            num_layers=NUM_LAYERS,
            horizon=HORIZON,
            dropout=DROPOUT,
            use_attention=False,
        )
        model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu", weights_only=True))
        model.eval()
        with torch.no_grad():
            scaled_pred = model(torch.tensor(scaled_seq)).numpy()

    point_pred = scaler.inverse_transform(scaled_pred.reshape(-1, 1)).flatten().tolist()
    mean_forecast = [max(0.0, round(float(val), 2)) for val in point_pred]

    # 2. Empirical 90% confidence intervals via Monte Carlo Dropout
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model checkpoint not found at '{MODEL_PATH}'. Run src/train.py first.")

    pt_model = MultiStepLSTM(
        input_size=1,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        horizon=HORIZON,
        dropout=DROPOUT,
        use_attention=False,
    )
    pt_model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu", weights_only=True))
    torch.manual_seed(RANDOM_SEED)

    lower_bound, upper_bound = compute_mc_dropout_bounds(
        pt_model, scaled_seq, scaler, n_iterations=mc_iterations
    )

    return {
        "mean_forecast": mean_forecast,
        "lower_bound_90": lower_bound,
        "upper_bound_90": upper_bound,
    }


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("RUNNING STANDALONE DEMAND PREDICTION DEMO")
    print("=" * 60)

    # Generate sample lookback sequence (45 days)
    sample_demand = [100.0 + i * 0.8 for i in range(LOOKBACK)]
    
    result = forecast_demand(sample_demand, use_onnx=True)

    print(f"Input Sequence Length : {len(sample_demand)} days")
    print(f"Horizon Forecast      : {len(result['mean_forecast'])} days\n")
    print(f"Mean Forecast (7-Day) : {result['mean_forecast']}")
    print(f"Lower Bound (90% CI)  : {result['lower_bound_90']}")
    print(f"Upper Bound (90% CI)  : {result['upper_bound_90']}")
    print("=" * 60 + "\n")