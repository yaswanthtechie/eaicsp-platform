import json
from pathlib import Path

import numpy as np
import torch
import onnx
import onnxruntime as ort

from src.global_model import GlobalDemandLSTM

CHECKPOINT_PATH = Path("output/global_best_model.pt")
ONNX_PATH = Path("output/global_best_model.onnx")

def main():
    if not CHECKPOINT_PATH.exists():
        raise FileNotFoundError(f"Checkpoint not found: {CHECKPOINT_PATH}")

    checkpoint = torch.load(
        CHECKPOINT_PATH,
        map_location="cpu",
        weights_only=False,
    )

    config = checkpoint["config"]
    lookback = int(checkpoint["lookback"])

    model = GlobalDemandLSTM(**config)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    # Sample inputs: 45 days, 4 numerical features.
    batch_size = 2
    x = torch.randn(batch_size, lookback, config["num_numeric_features"])
    sku_id = torch.tensor([1, 2], dtype=torch.long)
    category_id = torch.tensor([1, 2], dtype=torch.long)
    warehouse_id = torch.tensor([1, 2], dtype=torch.long)

    with torch.no_grad():
        pytorch_output = model(x, sku_id, category_id, warehouse_id)

    print("PyTorch output shape:", tuple(pytorch_output.shape))

    ONNX_PATH.parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        model,
        (x, sku_id, category_id, warehouse_id),
        str(ONNX_PATH),
        input_names=["x", "sku_id", "category_id", "warehouse_id"],
        output_names=["forecast"],
        dynamic_axes={
            "x": {0: "batch_size"},
            "sku_id": {0: "batch_size"},
            "category_id": {0: "batch_size"},
            "warehouse_id": {0: "batch_size"},
            "forecast": {0: "batch_size"},
        },
        opset_version=17,
        dynamo=False,
    )

    # Validate exported ONNX model.
    onnx_model = onnx.load(str(ONNX_PATH))
    onnx.checker.check_model(onnx_model)
    print("ONNX model validation: PASSED")

    # Compare PyTorch and ONNX predictions.
    session = ort.InferenceSession(
        str(ONNX_PATH),
        providers=["CPUExecutionProvider"],
    )

    ort_inputs = {
        "x": x.numpy().astype(np.float32),
        "sku_id": sku_id.numpy().astype(np.int64),
        "category_id": category_id.numpy().astype(np.int64),
        "warehouse_id": warehouse_id.numpy().astype(np.int64),
    }

    onnx_output = session.run(["forecast"], ort_inputs)[0]
    pytorch_array = pytorch_output.numpy()

    max_abs_diff = float(
        np.max(np.abs(pytorch_array - onnx_output))
    )
    parity_passed = bool(
        np.allclose(pytorch_array, onnx_output, rtol=1e-4, atol=1e-5)
    )

    report = {
        "checkpoint": str(CHECKPOINT_PATH),
        "onnx_model": str(ONNX_PATH),
        "opset": 17,
        "lookback": lookback,
        "horizon": config["horizon"],
        "sample_batch_size": batch_size,
        "pytorch_output_shape": list(pytorch_array.shape),
        "onnx_output_shape": list(onnx_output.shape),
        "max_absolute_difference": max_abs_diff,
        "parity_passed": parity_passed,
        "onnx_validation_passed": True,
        "execution_provider": "CPUExecutionProvider",
    }

    report_path = Path("output/global_onnx_export_report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("ONNX output shape:", onnx_output.shape)
    print("Maximum absolute difference:", max_abs_diff)
    print("Prediction parity:", "PASSED" if parity_passed else "FAILED")
    print("ONNX file:", ONNX_PATH)
    print("Report:", report_path)

    if not parity_passed:
        raise RuntimeError("PyTorch and ONNX predictions do not match.")

if __name__ == "__main__":
    main()
