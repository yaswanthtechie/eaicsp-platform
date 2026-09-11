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
