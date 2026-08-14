import pandas as pd

import etl.src.quality_gate as qg


def test_quality_gate_rejects_and_moves_file(tmp_path, monkeypatch):
    rejected_dir = tmp_path / "rejected"
    monkeypatch.setattr(qg, "REJECTED_DIR", rejected_dir)
    monkeypatch.setattr(qg, "write_alert", lambda **kwargs: None)

    batch_file = tmp_path / "sales_bad_batch.csv"
    batch_file.write_text("placeholder")

    df = pd.DataFrame({
        "date": pd.to_datetime(["2026-07-20"] * 10),
        "sku_id": ["SKU101"] * 10,
        "warehouse_id": ["WH1"] * 10,
        "quantity_sold": [-5] * 10,
        "unit_price": [100.0] * 10,
    })

    result = qg.quality_gate([
        {"file_path": batch_file, "data": df}
    ])

    assert result == []
    assert (rejected_dir / "sales_bad_batch.csv").exists()
    assert not batch_file.exists()
