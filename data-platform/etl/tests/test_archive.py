from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, text

import etl.src.archive as archive
from etl.src.config_loader import load_pipeline_config


def _engine(live_table, archive_table):
    engine = create_engine("sqlite://")
    columns = (
        "id INTEGER PRIMARY KEY, date TEXT, sku_id TEXT, warehouse_id TEXT, "
        "quantity_sold INTEGER, unit_price REAL, source_batch TEXT, "
        "run_id INTEGER, pipeline_version TEXT, loaded_at TEXT, updated_at TEXT"
    )
    old = (date.today() - timedelta(days=800)).isoformat()
    new = date.today().isoformat()
    with engine.begin() as c:
        c.execute(text(f"CREATE TABLE {live_table} ({columns})"))
        c.execute(text(f"CREATE TABLE {archive_table} ({columns})"))
        c.execute(text(
            f"INSERT INTO {live_table} (id, date, sku_id, warehouse_id) VALUES "
            f"(1, '{old}', 'S1', 'W1'), (2, '{new}', 'S2', 'W1')"
        ))
    return engine


@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
def test_archive_moves_old_rows_in_the_env_tables(env, monkeypatch):
    monkeypatch.setenv("ETL_ENV", env)
    config = load_pipeline_config()
    engine = _engine(config.archive.table, config.archive.archive_table)
    monkeypatch.setattr(archive, "get_engine", lambda: engine)

    result = archive.archive_old_sales(cutoff_days=730, run_id=1, config=config)

    assert result["live_table"] == config.archive.table
    assert (result["archived_count"], result["deleted_count"]) == (1, 1)
    with engine.connect() as c:
        live_ids = [r.id for r in c.execute(text(f"SELECT id FROM {config.archive.table}"))]
        archived_ids = [r.id for r in c.execute(text(f"SELECT id FROM {config.archive.archive_table}"))]
    assert live_ids == [2]
    assert archived_ids == [1]


def test_archive_is_idempotent(monkeypatch):
    monkeypatch.setenv("ETL_ENV", "dev")
    config = load_pipeline_config()
    engine = _engine(config.archive.table, config.archive.archive_table)
    monkeypatch.setattr(archive, "get_engine", lambda: engine)

    archive.archive_old_sales(cutoff_days=730, config=config)
    second = archive.archive_old_sales(cutoff_days=730, config=config)

    assert (second["archived_count"], second["deleted_count"]) == (0, 0)


def test_staging_and_prod_never_touch_dev_tables(monkeypatch):
    for env, prefix in [("staging", "staging_"), ("prod", "prod_")]:
        monkeypatch.setenv("ETL_ENV", env)
        config = load_pipeline_config()
        assert config.archive.table == f"{prefix}sales_fact"
        assert config.archive.archive_table == f"{prefix}sales_fact_archive"
