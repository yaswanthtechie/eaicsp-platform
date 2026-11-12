import pytest
import torch

from src.global_model import GlobalDemandLSTM, load_global_checkpoint


CONFIG = dict(
    num_skus=3,
    num_categories=2,
    num_warehouses=2,
    num_numeric_features=4,
    embedding_dim=8,
    hidden_size=64,
    num_layers=2,
    horizon=7,
    dropout=0.2,
)


def test_checkpoint_round_trip(tmp_path):
    torch.manual_seed(0)
    model = GlobalDemandLSTM(**CONFIG).eval()
    path = tmp_path / "ckpt.pt"

    torch.save({
        "state_dict": model.state_dict(),
        "config": CONFIG,
        "scaler_mean": [0.0],
        "scaler_scale": [1.0],
        "sku_mapping": {"A": 1, "B": 2},
        "category_mapping": {"C": 1},
        "warehouse_mapping": {"W": 1},
        "lookback": 5,
    }, path)

    loaded, _ = load_global_checkpoint(path)

    x = torch.randn(2, 5, 4)
    sku = torch.tensor([1, 2])
    other = torch.tensor([1, 1])

    with torch.no_grad():
        assert torch.allclose(
            model(x, sku, other, other),
            loaded(x, sku, other, other),
        )


def test_old_checkpoint_format_is_rejected(tmp_path):
    path = tmp_path / "old.pt"
    torch.save({"model_state_dict": {}, "num_skus": 3}, path)

    with pytest.raises(ValueError, match="missing keys"):
        load_global_checkpoint(path)
