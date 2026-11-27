"""
Round 5 Full PyTest Suite: ONNX Parity & Adversarial Robustness
"""

import os

import numpy as np
import onnxruntime as ort
import pytest
import torch
from sklearn.preprocessing import MinMaxScaler

import predict as predict_module
from config import (
    DROPOUT,
    HIDDEN_SIZE,
    HORIZON,
    LOOKBACK,
    MODEL_PATH,
    NUM_LAYERS,
)
from model import MultiStepLSTM
from onnx_export import export_and_verify_onnx
from predict import forecast_demand
from src.data import save_scaler


def test_onnx_export_and_strict_parity(tmp_path):
    """Validates PyTorch and ONNX Runtime produce identical outputs."""
    test_onnx_path = str(tmp_path / "best_model.onnx")

    export_and_verify_onnx(onnx_path=test_onnx_path)

    so = ort.SessionOptions()
    so.log_severity_level = 3
    session = ort.InferenceSession(
        test_onnx_path,
        sess_options=so,
        providers=["CPUExecutionProvider"],
    )

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
        model.load_state_dict(
            torch.load(MODEL_PATH, map_location="cpu", weights_only=True)
        )
    model.eval()

    with torch.no_grad():
        torch_pred = model(torch.tensor(dummy_input)).numpy()

    onnx_pred = session.run(None, {session.get_inputs()[0].name: dummy_input})[0]
    np.testing.assert_allclose(torch_pred, onnx_pred, rtol=1e-4, atol=1e-5)


@pytest.mark.parametrize(
    "corrupted_input",
    [
        [100.0] * (LOOKBACK - 1) + [10000.0],  # Extreme spike
        [-50.0] * LOOKBACK,  # All negative
        [0.0] * LOOKBACK,  # All zeros
        [100.0] * (LOOKBACK - 5) + [float("nan")] * 5,  # NaNs
    ],
)
def test_adversarial_input_handling(corrupted_input, tmp_path, monkeypatch):
    """Verifies adversarial inputs using isolated temporary model artifacts."""
    scaler_path = tmp_path / "scaler.json"
    model_path = tmp_path / "model.pt"
    onnx_path = tmp_path / "model.onnx"

    scaler = MinMaxScaler()
    scaler.fit(np.array([[0.0], [1000.0]], dtype=np.float32))
    save_scaler(scaler, str(scaler_path))

    model = MultiStepLSTM(
        input_size=1,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        horizon=HORIZON,
        dropout=DROPOUT,
        use_attention=False,
    )
    torch.save(model.state_dict(), model_path)

    monkeypatch.setattr(predict_module, "SCALER_PATH", str(scaler_path))
    monkeypatch.setattr(predict_module, "MODEL_PATH", str(model_path))
    monkeypatch.setattr(predict_module, "ONNX_PATH", str(onnx_path))

    result = forecast_demand(corrupted_input, mc_iterations=5)
    forecast = result["mean_forecast"]

    assert len(forecast) == HORIZON
    assert not np.isnan(forecast).any()
    assert not np.isinf(forecast).any()
    assert all(x >= 0.0 for x in forecast)


def test_invalid_sequence_length_rejection():
    """Verifies input sequences of incorrect length are rejected."""
    with pytest.raises(ValueError, match="Expected sequence length"):
        forecast_demand([100.0] * 10)
