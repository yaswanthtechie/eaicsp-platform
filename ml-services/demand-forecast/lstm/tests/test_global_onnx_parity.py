import numpy as np
import pytest
import torch

onnx = pytest.importorskip("onnx")
ort = pytest.importorskip("onnxruntime")

from src.global_model import GlobalDemandLSTM
from src.global_onnx_export import export_model


def test_global_lstm_onnx_matches_pytorch(tmp_path):
    torch.manual_seed(42)

    model = GlobalDemandLSTM(
        num_skus=5,
        num_categories=3,
        num_warehouses=2,
        num_numeric_features=4,
        embedding_dim=4,
        hidden_size=8,
        num_layers=1,
        horizon=3,
        dropout=0.0,
    )
    model.eval()

    sample = (
        torch.randn(2, 12, 4),
        torch.tensor([1, 2], dtype=torch.long),
        torch.tensor([1, 2], dtype=torch.long),
        torch.tensor([1, 1], dtype=torch.long),
    )

    onnx_path = tmp_path / "global_model.onnx"
    export_model(model, sample, onnx_path)

    with torch.no_grad():
        pytorch_output = model(*sample).cpu().numpy()

    session = ort.InferenceSession(
        str(onnx_path),
        providers=["CPUExecutionProvider"],
    )

    ort_inputs = {
        "input_sequence": sample[0].numpy(),
        "sku_id": sample[1].numpy(),
        "category_id": sample[2].numpy(),
        "warehouse_id": sample[3].numpy(),
    }
    onnx_output = session.run(None, ort_inputs)[0]

    np.testing.assert_allclose(
        onnx_output,
        pytorch_output,
        rtol=1e-5,
        atol=1e-5,
    )
