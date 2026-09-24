import os
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine, text
from etl.src.config_loader import load_pipeline_config
from etl.src.lineage import trace_row_lineage

def _engine():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        for table, date_col in [("sales_fact", "date"),
                                ("inventory_snapshot", "snapshot_date"),
                                ("shipments_fact", "shipment_date")]:
            c.execute(text(
                f"CREATE TABLE {table} (id INTEGER, {date_col} TEXT, sku_id TEXT, "
                f"warehouse_id TEXT, run_id INTEGER, source_batch TEXT)"
            ))
        c.execute(text("INSERT INTO sales_fact VALUES (10,'2024-01-01','S1','W1',100,'s.csv')"))
        c.execute(text("INSERT INTO inventory_snapshot VALUES (20,'2024-01-01','S1','W1',200,'i.csv')"))
        c.execute(text("INSERT INTO shipments_fact VALUES (30,'2024-01-01','S1','W1',300,'sh.csv')"))
    return engine

def test_lineage_against_real_schema_columns():
    def src(name, table, date_column, depends_on):
        return SimpleNamespace(name=name, table=table, date_column=date_column,
                               depends_on=depends_on, lineage_keys=["sku_id", "warehouse_id"])
    by_name = {
        "sales": src("sales", "sales_fact", "date", None),
        "inventory": src("inventory", "inventory_snapshot", "snapshot_date", "sales"),
        "shipments": src("shipments", "shipments_fact", "shipment_date", "inventory"),
    }
    config = SimpleNamespace(sources=list(by_name.values()), get_source=by_name.__getitem__)
    lineage = trace_row_lineage(30, "shipments_fact", config=config, engine=_engine())
    assert [(r["table"], r["run_id"]) for r in lineage] == [
        ("shipments_fact", 300), ("inventory_snapshot", 200), ("sales_fact", 100),
    ]

@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
def test_every_env_config_has_lineage_keys(env, monkeypatch):
    monkeypatch.setenv("ETL_ENV", env)
    config = load_pipeline_config()
    for source in config.sources:
        assert source.lineage_keys == ["sku_id", "warehouse_id"], (env, source.name)

def test_lineage_with_real_dev_config():
    os.environ["ETL_ENV"] = "dev"
    lineage = trace_row_lineage(30, "shipments_fact",
                                config=load_pipeline_config(), engine=_engine())
    assert [r["run_id"] for r in lineage] == [300, 200, 100]
