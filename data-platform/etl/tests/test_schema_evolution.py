import pandas as pd
import pytest
from etl.src.data_contract import validate_no_unexpected_columns

def test_new_column_is_detected():
    df=pd.DataFrame({"date":pd.to_datetime(["2024-01-01"]),"sku_id":["S"],"warehouse_id":["W"],"quantity_sold":[1],"unit_price":[2.0],"discount":[0.1]})
    with pytest.raises(ValueError, match="Unexpected columns"):
        validate_no_unexpected_columns(df, {"date":{},"sku_id":{},"warehouse_id":{},"quantity_sold":{},"unit_price":{}})


def test_quarantine_moves_file(tmp_path):
    from types import SimpleNamespace
    from etl.src.schema_evolution import handle_schema_evolution
    source = tmp_path / "input.csv"
    source.write_text("x,y\n1,2\n")
    cfg = SimpleNamespace(schema_evolution="quarantine")
    destination = handle_schema_evolution(source, cfg, project_root=tmp_path)
    assert not source.exists()
    assert destination.exists()
    assert destination.parent.name == "quarantine"


def test_quarantine_adds_unique_suffix_for_same_filename(tmp_path):
    from types import SimpleNamespace
    from etl.src.schema_evolution import handle_schema_evolution
    cfg = SimpleNamespace(schema_evolution="quarantine")
    first = tmp_path / "input.csv"
    first.write_text("x\n1\n")
    d1 = handle_schema_evolution(first, cfg, project_root=tmp_path)
    second = tmp_path / "input.csv"
    second.write_text("x\n2\n")
    d2 = handle_schema_evolution(second, cfg, project_root=tmp_path)
    assert d1 != d2
    assert d1.exists() and d2.exists()
