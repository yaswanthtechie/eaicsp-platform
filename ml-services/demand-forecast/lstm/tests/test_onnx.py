"""
Stretch goal (R4/R5) -- verify ONNX model predictions match PyTorch predictions
identically, for both Plain MultiStepLSTM and Attention MultiStepLSTM.

Requires onnx + onnxruntime:
    pip install onnx onnxruntime

Run with: python -m pytest tests/test_onnx.py -v
Or directly: python tests/test_onnx.py
"""

import os
import sys
import warnings

# Ensure src/ directory is importable when executed directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import numpy as np
import pytest
import torch

from config import HORIZON, LOOKBACK
import model as model_module
from model import MultiStepLSTM
from onnx_export import export_to_onnx

try:
    import onnxruntime as ort
    ONNXRUNTIME_AVAILABLE = True
except ImportError:
    ONNXRUNTIME_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not ONNXRUNTIME_AVAILABLE,
    reason="onnxruntime not installed -- run `pip install onnx onnxruntime` to enable this test",
)


def _assert_onnx_matches_pytorch(model: torch.nn.Module, tmp_path, filename: str):
    """Exports and verifies numerical parity between PyTorch and ONNX Runtime."""
    model.eval()
    dummy_input = torch.randn(2, LOOKBACK, 1, dtype=torch.float32)
    onnx_file = os.path.join(str(tmp_path), filename)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        export_to_onnx(model=model, dummy_input=dummy_input, onnx_path=onnx_file)

    with torch.no_grad():
        pt_out = model(dummy_input).cpu().numpy()

    so = ort.SessionOptions()
    so.log_severity_level = 3
    ort_session = ort.InferenceSession(onnx_file, sess_options=so, providers=["CPUExecutionProvider"])
    
    ort_inputs = {ort_session.get_inputs()[0].name: dummy_input.numpy()}
    ort_out = ort_session.run(None, ort_inputs)[0]

    max_diff = float(np.max(np.abs(pt_out - ort_out)))
    assert np.allclose(pt_out, ort_out, rtol=1e-4, atol=1e-5), (
        f"ONNX outputs do not match PyTorch outputs for {filename}: max abs diff = {max_diff:.8e}"
    )


def test_onnx_identity_prediction_plain_lstm(tmp_path):
    """Plain MultiStepLSTM: ONNX Runtime output must match PyTorch output."""
    torch.manual_seed(42)
    model = MultiStepLSTM(
        input_size=1,
        hidden_size=32,
        num_layers=1,
        horizon=HORIZON,
        dropout=0.0,
        use_attention=False,
    )
    _assert_onnx_matches_pytorch(model, tmp_path, "plain_model.onnx")


def test_onnx_identity_prediction_attention_lstm(tmp_path):
    """Attention LSTM: ONNX export must handle attention layers (bmm/softmax)
    correctly and match PyTorch output within numerical tolerance."""
    torch.manual_seed(42)
    
    # Support both unified MultiStepLSTM(use_attention=True) and legacy AttentionMultiStepLSTM
    if hasattr(model_module, "AttentionMultiStepLSTM"):
        model = model_module.AttentionMultiStepLSTM(
            input_size=1, hidden_size=32, num_layers=1, horizon=HORIZON
        )
    else:
        model = MultiStepLSTM(
            input_size=1,
            hidden_size=32,
            num_layers=1,
            horizon=HORIZON,
            dropout=0.0,
            use_attention=True,
        )
        
    _assert_onnx_matches_pytorch(model, tmp_path, "attention_model.onnx")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))