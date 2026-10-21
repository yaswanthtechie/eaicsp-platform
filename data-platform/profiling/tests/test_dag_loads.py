import pytest

pytest.importorskip("airflow.models.dagbag")   # Airflow lives in the container, not the main venv


def test_profiling_dag_loads():
    from airflow.models import DagBag

    bag = DagBag(dag_folder="dags", include_examples=False)
    assert bag.import_errors == {}

    dag = bag.get_dag("scheduled_data_profiling")
    assert dag is not None
    assert {t.task_id for t in dag.tasks} == {
        "profile_table_benchmark_1m_sales",
        "profile_table_products",
    }