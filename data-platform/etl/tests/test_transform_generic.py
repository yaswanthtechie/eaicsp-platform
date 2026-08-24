import pandas as pd
import pytest

from etl.src.transform import transform_data_generic
from etl.src.config_loader import load_pipeline_config


CONFIG = load_pipeline_config()
INVENTORY_CONFIG = CONFIG.get_source("inventory")


def test_transform_casts_types_and_drops_duplicates():
    df = pd.DataFrame({
        "snapshot_date": ["2024-01-01", "2024-01-01"],
        "sku_id": ["SKU1", "SKU1"],
        "warehouse_id": ["WH1", "WH1"],
        "quantity_on_hand": ["10", "10"],  # duplicate row, string quantity
    })

    result = transform_data_generic([df], INVENTORY_CONFIG)

    assert len(result) == 1
    out = result[0]
    assert len(out) == 1  # duplicate dropped
    assert pd.api.types.is_datetime64_any_dtype(out["snapshot_date"])
    assert pd.api.types.is_integer_dtype(out["quantity_on_hand"])


def test_transform_empty_list_returns_empty_list():
    result = transform_data_generic([], INVENTORY_CONFIG)
    assert result == []


def test_transform_failure_raises_and_does_not_silently_drop(monkeypatch):
    from etl.src import transform as transform_module
    monkeypatch.setattr(transform_module, "write_alert", lambda **kwargs: None)

    df = pd.DataFrame({
        "snapshot_date": ["2024-01-01"],
        "sku_id": ["SKU1"],
        "warehouse_id": ["WH1"],
        "quantity_on_hand": ["not_a_number"],
    })

    with pytest.raises(ValueError):
        transform_data_generic([df], INVENTORY_CONFIG)
