import csv
import shutil
from pathlib import Path

import pytest
import yaml

ETL_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ETL_ROOT / "client_ingest" / "samples" / "client_format"


def test_bad_reference_fails_quality_check(tmp_path):
    from client_ingest.quality_checks import evaluate_quality

    folder = tmp_path / "client"
    shutil.copytree(SAMPLE_DIR, folder)

    sales_file = folder / "sales_history.csv"
    with sales_file.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames
        rows = list(reader)

    rows[0]["product_code"] = "UNKNOWN-PRODUCT-999"

    with sales_file.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    thresholds = yaml.safe_load(
        (ETL_ROOT / "client_ingest" / "quality_thresholds.yaml").read_text()
    )
    thresholds["freshness"]["max_age_days"] = 9999
    thresholds["freshness"]["per_file_max_age_days"] = {
        "supplier_lead_times": 9999,
        "supplier_incidents": 9999,
    }

    report = evaluate_quality(folder, thresholds)

    assert report["trusted"] is False
    assert any("unknown master references" in reason for reason in report["reasons"])


def test_client_data_load_dag_imports_and_orders_tasks():
    import os
    import sys

    if os.name == "nt":
        pytest.skip("Airflow DAG imports require Linux; run this test in Airflow Docker")

    import importlib.util

    dag_file = ETL_ROOT / "dags" / "client_data_load_dag.py"
    spec = importlib.util.spec_from_file_location("client_data_load_dag_test", dag_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    dag = module.dag
    assert dag.schedule is None
    assert set(dag.task_ids) == {
        "load_client_files", "build_client_kpis", "check_client_quality"
    }
    assert dag.get_task("load_client_files").downstream_task_ids == {
        "build_client_kpis"
    }
    assert dag.get_task("build_client_kpis").downstream_task_ids == {
        "check_client_quality"
    }
