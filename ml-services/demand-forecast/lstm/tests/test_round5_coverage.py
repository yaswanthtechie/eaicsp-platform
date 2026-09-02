"""
Round 5 Full PyTest Suite: ONNX Parity & Adversarial Robustness
"""

import os
import numpy as np
import onnxruntime as ort
import pytest
import torch

from config import (
    DROPOUT,
    HIDDEN_SIZE,
    HORIZON,
    LOOKBACK,
    MODEL_PATH,
    NUM_LAYERS,
    ONNX_PATH,
    SCALER_PATH,
)
from model import MultiStepLSTM
from onnx_export import export_and_verify_onnx
from predict import forecast_demand, sanitize_input_sequence


def test_onnx_export_and_strict_parity():
    """Validates PyTorch and ONNX Runtime produce identical outputs."""
    export_and_verify_onnx()

    so = ort.SessionOptions()
    so.log_severity_level = 3
    session = ort.InferenceSession(ONNX_PATH, sess_options=so, providers=["CPUExecutionProvider"])
    
    np.random.seed(42)
    dummy_input = np.random.randn(2, LOOKBACK, 1).astype(np.float32)

    model = MultiStepLSTM(
        input_size=1,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        horizon=HORIZON,
        dropout=DROPOUT,
        use_attention=False,
    )
    if os.path.exists(MODEL_PATH):
        model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu", weights_only=True))
    model.eval()

    with torch.no_grad():
        torch_pred = model(torch.tensor(dummy_input)).numpy()

    onnx_pred = session.run(None, {session.get_inputs()[0].name: dummy_input})[0]
    np.testing.assert_allclose(torch_pred, onnx_pred, rtol=1e-4, atol=1e-5)


@pytest.mark.parametrize(
    "corrupted_input",
    [
        [100.0] * (LOOKBACK - 1) + [10000.0],           # Extreme spike
        [-50.0] * LOOKBACK,                             # All negative
        [0.0] * LOOKBACK,                               # All zeros
        [100.0] * (LOOKBACK - 5) + [float("nan")] * 5,  # NaNs
    ],
)
def test_adversarial_input_handling(corrupted_input):
    """Verifies that adversarial inputs do not crash and return valid positive forecasts."""
    result = forecast_demand(corrupted_input)
    forecast = result["mean_forecast"]

    assert len(forecast) == HORIZON
    assert not np.isnan(forecast).any()
    assert not np.isinf(forecast).any()
    assert all(x >= 0.0 for x in forecast)


def test_invalid_sequence_length_rejection():
    """Verifies input sequences of incorrect length are rejected."""
    with pytest.raises(ValueError, match="Expected sequence length"):
        forecast_demand([100.0] * 10)