"""
ONNX Model Export and Strict Parity Verification
"""

import os
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import onnxruntime as ort
import torch

from config import HORIZON, LOOKBACK, MODEL_PATH, ONNX_PATH
from model import MultiStepLSTM


def export_to_onnx(
    model: torch.nn.Module = None,
    dummy_input: torch.Tensor = None,
    onnx_path: str = None,
    output_path: str = None,
    lookback: int = LOOKBACK,
    horizon: int = HORIZON,
    pytorch_model_path: str = MODEL_PATH,
    **kwargs,
) -> str:
    """Exports PyTorch model to ONNX, supporting all test harness signatures."""
    target_path = onnx_path or output_path or ONNX_PATH
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

    if model is None:
        model = MultiStepLSTM(
            input_size=1,
            hidden_size=64,
            num_layers=2,
            horizon=horizon,
            dropout=0.0,
            use_attention=False,
        )
        if os.path.exists(pytorch_model_path):
            model.load_state_dict(torch.load(pytorch_model_path, map_location="cpu", weights_only=True))

    model.eval()

    if dummy_input is None:
        dummy_input = torch.randn(1, lookback, 1, dtype=torch.float32)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        torch.onnx.export(
            model,
            dummy_input,
            target_path,
            export_params=True,
            opset_version=18,
            do_constant_folding=True,
            input_names=["input_sequence"],
            output_names=["forecast"],
            dynamic_axes={
                "input_sequence": {0: "batch_size"},
                "forecast": {0: "batch_size"},
            },
            dynamo=False,
        )
    return target_path


def verify_onnx_parity(
    model: torch.nn.Module = None,
    onnx_path: str = ONNX_PATH,
    lookback: int = LOOKBACK,
    horizon: int = HORIZON,
):
    if model is None:
        model = MultiStepLSTM(input_size=1, hidden_size=64, num_layers=2, horizon=horizon, dropout=0.0)
        if os.path.exists(MODEL_PATH):
            model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu", weights_only=True))
    model.eval()

    so = ort.SessionOptions()
    so.log_severity_level = 3
    ort_session = ort.InferenceSession(onnx_path, sess_options=so, providers=["CPUExecutionProvider"])

    test_input_np = np.random.randn(4, lookback, 1).astype(np.float32)
    test_input_torch = torch.tensor(test_input_np)

    with torch.no_grad():
        torch_out = model(test_input_torch).cpu().numpy()

    ort_inputs = {ort_session.get_inputs()[0].name: test_input_np}
    ort_out = ort_session.run(None, ort_inputs)[0]

    max_diff = float(np.max(np.abs(torch_out - ort_out)))
    print(f"[PARITY CHECK] Max Absolute Difference: {max_diff:.8e}")

    np.testing.assert_allclose(torch_out, ort_out, rtol=1e-4, atol=1e-5)
    print("[VERIFIED] ONNX Runtime output identically matches PyTorch output.\n")


def export_and_verify_onnx(*args, **kwargs):
    export_to_onnx(*args, **kwargs)
    verify_onnx_parity()


if __name__ == "__main__":
    export_to_onnx()
    verify_onnx_parity()