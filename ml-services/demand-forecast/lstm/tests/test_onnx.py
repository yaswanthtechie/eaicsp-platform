"""
Stretch goal (R4) -- verify ONNX model predictions match PyTorch predictions
identically, for both MultiStepLSTM and AttentionMultiStepLSTM.

Requires onnx + onnxruntime:
    pip install onnx onnxruntime

Run with: python -m pytest tests/test_onnx.py -v
"""
import sys
import os
import warnings

import numpy as np
import pytest
import torch


from model import MultiStepLSTM, AttentionMultiStepLSTM  # noqa: E402
from onnx_export import export_to_onnx  # noqa: E402

try:
    import onnxruntime as ort
    ONNXRUNTIME_AVAILABLE = True
except ImportError:
    ONNXRUNTIME_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not ONNXRUNTIME_AVAILABLE,
    reason="onnxruntime not installed -- run `pip install onnx onnxruntime` to enable this test",
)


def _assert_onnx_matches_pytorch(model, tmp_path, filename):
    model.eval()
    dummy_input = torch.randn(1, 30, 1, dtype=torch.float32)
    onnx_file = os.path.join(tmp_path, filename)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        export_to_onnx(model, dummy_input, onnx_path=onnx_file)

    with torch.no_grad():
        pt_out = model(dummy_input).numpy()

    ort_session = ort.InferenceSession(onnx_file)
    ort_inputs = {ort_session.get_inputs()[0].name: dummy_input.numpy()}
    ort_out = ort_session.run(None, ort_inputs)[0]

    assert np.allclose(pt_out, ort_out, atol=1e-5), (
        f"ONNX outputs do not match PyTorch outputs for {filename}: "
        f"max abs diff = {np.abs(pt_out - ort_out).max()}"
    )


def test_onnx_identity_prediction_plain_lstm(tmp_path):
    """Plain MultiStepLSTM: ONNX Runtime output must match PyTorch output."""
    model = MultiStepLSTM(input_size=1, hidden_size=32, num_layers=1, horizon=7)
    _assert_onnx_matches_pytorch(model, tmp_path, "plain_model.onnx")


def test_onnx_identity_prediction_attention_lstm(tmp_path):
    """AttentionMultiStepLSTM: ONNX export must handle the attention layers
    (bmm/softmax) correctly and still match PyTorch output exactly."""
    model = AttentionMultiStepLSTM(input_size=1, hidden_size=32, num_layers=1, horizon=7)
    _assert_onnx_matches_pytorch(model, tmp_path, "attention_model.onnx")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))