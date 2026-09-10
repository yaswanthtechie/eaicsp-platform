import os
import sys
from pathlib import Path

import pytest


# Airflow's local PythonOperator import requires Unix-only fcntl.
# The production Airflow environment runs in Docker/Linux, so this
# DagBag test is skipped when pytest is run directly on Windows.
if sys.platform == "win32":
    pytest.skip(
        "DagBag import test requires the Linux Airflow runtime used by Docker.",
        allow_module_level=True,
    )


# Airflow requires an absolute SQLite path.
AIRFLOW_DB = Path(__file__).resolve().parent / "airflow_test.db"

os.environ["AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"] = (
    "sqlite:////"
    + str(AIRFLOW_DB.resolve()).replace("\\", "/").lstrip("/")
)

from airflow.models import DagBag


def test_sales_runs_before_inventory():
    dag_folder = Path(__file__).resolve().parents[1] / "dags"

    dag_bag = DagBag(
        dag_folder=str(dag_folder),
        include_examples=False,
    )

    assert not dag_bag.import_errors, dag_bag.import_errors

    dag = dag_bag.get_dag("sales_etl_pipeline")
    assert dag is not None

    sales_join = dag.get_task("join_sales")
    inventory_extract = dag.get_task("extract_inventory")

    assert sales_join.task_id in {
        task.task_id
        for task in inventory_extract.upstream_list
    }     