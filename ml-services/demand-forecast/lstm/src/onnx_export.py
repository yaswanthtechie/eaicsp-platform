"""
Stretch goal (R4) -- export the trained model via ONNX, prove it loads and
predicts identically outside PyTorch.

Kept as its own module rather than folded into model.py, so model.py stays
purely architecture definitions.
"""

import torch


def export_to_onnx(model, dummy_input: torch.Tensor, onnx_path: str = "output/model.onnx") -> str:
    """
    Exports a trained MultiStepLSTM / AttentionMultiStepLSTM to ONNX.

    Args:
        model: a trained model instance, already in eval() mode by the caller
            if you want deterministic (non-MC-Dropout) export -- this function
            does not force eval()/train() mode, so it also works for exporting
            an MC-Dropout-enabled model if that's ever needed.
        dummy_input: a representative input tensor, shape [1, lookback, 1],
            used only to trace the graph.
        onnx_path: output file path.

    Returns:
        The onnx_path it wrote to.
    """
    torch.onnx.export(
        model,
        dummy_input,
        onnx_path,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
    )
    print(f"Model exported to {onnx_path}")
    return onnx_path


if __name__ == "__main__":
    import os
    from data import generate_data, get_walk_forward_folds
    from model import MultiStepLSTM
    from train_utils import train_model, build_model

    LOOKBACK = 30
    HORIZON = 7

    df = generate_data(days=1000)
    folds = get_walk_forward_folds(df, n_folds=5, lookback=LOOKBACK, horizon=HORIZON,
                                    save_scaler_path=None)
    X_tr, y_tr, X_te, y_te, scaler = folds[-1]

    model = build_model(MultiStepLSTM, hidden_size=64, num_layers=2, horizon=HORIZON)
    model = train_model(model, X_tr, y_tr, epochs=25)
    model.eval()

    os.makedirs("output", exist_ok=True)
    dummy_input = torch.randn(1, LOOKBACK, 1, dtype=torch.float32)
    export_to_onnx(model, dummy_input, onnx_path="output/model.onnx")

    with torch.no_grad():
        pt_out = model(dummy_input).numpy()
    print("PyTorch output on dummy input:", pt_out)
    print("Run tests/test_onnx.py to verify ONNX Runtime reproduces this identically.")