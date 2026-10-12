import sys
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip("DagBag import needs the Linux Airflow runtime (Docker).", allow_module_level=True)

from airflow.models import DagBag


def test_spark_backfill_dag_is_manual_only():
    dag_folder = Path(__file__).resolve().parents[2] / "dags"
    bag = DagBag(dag_folder=str(dag_folder), include_examples=False)
    assert not bag.import_errors, bag.import_errors
    dag = bag.get_dag("sales_spark_historical_backfill")
    assert dag is not None
    assert dag.schedule_interval is None
    assert dag.max_active_runs == 1
    assert "spark_monthly_backfill" in dag.task_ids