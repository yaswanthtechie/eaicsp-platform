"""Export the trained GlobalDemandLSTM using real held-out test inputs."""

from pathlib import Path

import numpy as np
import onnx
import torch

from src.config import GLOBAL_DATA_PATH, GLOBAL_LOOKBACK, GLOBAL_HORIZON
from src.global_data import load_global_data
from src.global_model import load_global_checkpoint


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
CHECKPOINT_PATH = OUTPUT / "global_best_model.pt"
ONNX_PATH = OUTPUT / "global_best_model.onnx"
DATA_PATH = ROOT / GLOBAL_DATA_PATH


def main():
    if not CHECKPOINT_PATH.exists():
        raise FileNotFoundError(
            f"Checkpoint missing: {CHECKPOINT_PATH}. "
            "Run python -m src.global_train first."
        )

    data = load_global_data(
        DATA_PATH,
        lookback=GLOBAL_LOOKBACK,
        horizon=GLOBAL_HORIZON,
    )
    model, checkpoint = load_global_checkpoint(CHECKPOINT_PATH)
    model.eval()

    # Confirm that inference data uses the same categorical IDs as training.
    for key in ("sku_mapping", "category_mapping", "warehouse_mapping"):
        if getattr(data, key) != checkpoint[key]:
            raise ValueError(
                f"{key} differs between checkpoint and current dataset."
            )

    x, sku, category, warehouse, target = data.test.tensors

    if len(x) == 0:
        raise ValueError("Global test dataset is empty.")

    # Export using an actual held-out test sample, not random input.
    sample = (
        x[:2],
        sku[:2],
        category[:2],
        warehouse[:2],
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        model,
        sample,
        str(ONNX_PATH),
        input_names=[
            "input_sequence",
            "sku_id",
            "category_id",
            "warehouse_id",
        ],
        output_names=["forecast"],
        dynamic_axes={
            "input_sequence": {0: "batch"},
            "sku_id": {0: "batch"},
            "category_id": {0: "batch"},
            "warehouse_id": {0: "batch"},
            "forecast": {0: "batch"},
        },
        opset_version=17,
        dynamo=False,
    )

    graph = onnx.load(str(ONNX_PATH))
    onnx.checker.check_model(graph)

    # Verify ONNX output against PyTorch on real held-out windows.
    import onnxruntime as ort

    session = ort.InferenceSession(
        str(ONNX_PATH),
        providers=["CPUExecutionProvider"],
    )

    max_diff = 0.0
    for start in range(0, len(x), 128):
        end = min(start + 128, len(x))
        inputs = {
            "input_sequence": x[start:end].numpy(),
            "sku_id": sku[start:end].numpy(),
            "category_id": category[start:end].numpy(),
            "warehouse_id": warehouse[start:end].numpy(),
        }

        with torch.no_grad():
            pt = model(
                x[start:end],
                sku[start:end],
                category[start:end],
                warehouse[start:end],
            ).cpu().numpy()

        ort_output = session.run(["forecast"], inputs)[0]
        max_diff = max(
            max_diff,
            float(np.max(np.abs(pt - ort_output))),
        )

        if not np.allclose(pt, ort_output, rtol=1e-4, atol=1e-5):
            raise AssertionError(
                f"PyTorch/ONNX mismatch in rows {start}:{end}; "
                f"max difference={max_diff}"
            )

    print("Global ONNX export successful.")
    print(f"Checkpoint: {CHECKPOINT_PATH}")
    print(f"ONNX: {ONNX_PATH}")
    print(f"Real test windows verified: {len(x)}")
    print(f"Input shape: {tuple(x.shape)}")
    print(f"Output shape: ({len(x)}, {GLOBAL_HORIZON})")
    print(f"Maximum PyTorch/ONNX difference: {max_diff:.8e}")
    print(f"ONNX size: {ONNX_PATH.stat().st_size / 1024:.2f} KB")


if __name__ == "__main__":
    main()
