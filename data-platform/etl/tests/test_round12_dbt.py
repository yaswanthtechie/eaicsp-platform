from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DBT_ROOT = PROJECT_ROOT / "dbt"


def test_dbt_project_has_staging_and_marts():
    assert (DBT_ROOT / "dbt_project.yml").exists()
    assert (DBT_ROOT / "models" / "staging" / "stg_sales_fact.sql").exists()
    assert (DBT_ROOT / "models" / "staging" / "stg_inventory_snapshot.sql").exists()
    assert (DBT_ROOT / "models" / "staging" / "stg_shipments_fact.sql").exists()
    assert (DBT_ROOT / "models" / "marts" / "mart_daily_sales_by_warehouse.sql").exists()
    assert (DBT_ROOT / "models" / "marts" / "mart_inventory_position.sql").exists()


def test_dbt_tests_include_required_generic_and_custom_checks():
    schema = (DBT_ROOT / "models" / "marts" / "schema.yml").read_text()
    custom = (DBT_ROOT / "tests" / "mart_daily_sales_non_negative.sql").read_text()
    assert "not_null" in schema
    assert "unique" in schema
    assert "relationships" in schema
    assert "units_sold < 0" in custom
    assert "sales_amount < 0" in custom


def test_dag_runs_dbt_before_clickhouse_and_archive():
    dag = (PROJECT_ROOT / "dags" / "sales_etl_dag.py").read_text()
    assert 'task_id="dbt_build"' in dag
    assert 'task_id="clickhouse_load"' in dag
    assert "log_run >> dbt_build >> clickhouse_load >> archive_old_data" in dag
    assert 'task_id="finalize_run"' in dag
