"""
R9 M2: the DAG quality-gate task must hand validated batches to load,
report rejected ROWS, and route a fully rejected run to reject.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

DAG_FILE = Path(__file__).resolve().parents[1] / "dags" / "sales_etl_dag.py"


@pytest.fixture
def dag_module(monkeypatch):
    for name in ("airflow", "airflow.operators", "airflow.operators.python"):
        monkeypatch.setitem(sys.modules, name, MagicMock())

    spec = importlib.util.spec_from_file_location(
        "sales_etl_dag_under_test", DAG_FILE
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stub_quality_gate(monkeypatch, passing_file_names):
    fake = types.ModuleType("etl.src.quality_gate")
    fake.quality_gate_generic = lambda batches, config: [
        batch
        for batch in batches
        if Path(batch["file_path"]).name in passing_file_names
    ]
    monkeypatch.setitem(sys.modules, "etl.src.quality_gate", fake)


class FakeTaskInstance:
    def __init__(self, raw_batches):
        self.raw_batches = raw_batches
        self.pushed = {}

    def xcom_pull(self, task_ids=None, key="return_value"):
        if key in ("return_value", "raw_batches"):
            return self.raw_batches
        return None

    def xcom_push(self, key, value):
        self.pushed[key] = value


def _batches():
    return [
        {
            "file_path": Path("sales_good.csv"),
            "data": [{"quantity_sold": 5}] * 1000,
        },
        {
            "file_path": Path("sales_bad.csv"),
            "data": [{"quantity_sold": -1}] * 1000,
        },
    ]


def _gate(dag_module):
    return dag_module.make_quality_gate_task(
        types.SimpleNamespace(name="sales"),
        "extract_sales",
        "load_sales",
        "reject_sales",
    )


def test_gate_passes_validated_batches_to_load_and_counts_rejected_rows(
    dag_module, monkeypatch
):
    _stub_quality_gate(monkeypatch, {"sales_good.csv"})
    ti = FakeTaskInstance(_batches())

    branch = _gate(dag_module)(ti=ti)

    assert branch == "load_sales"
    assert ti.pushed["rows_rejected_pre_load"] == 1000
    assert "validated_batches" in ti.pushed

    loaded_files = [
        b["file_path"] for b in ti.pushed["validated_batches"]
    ]
    assert [Path(p).name for p in loaded_files] == ["sales_good.csv"]


def test_gate_routes_to_reject_when_every_file_fails(dag_module, monkeypatch):
    _stub_quality_gate(monkeypatch, set())
    ti = FakeTaskInstance(_batches())

    branch = _gate(dag_module)(ti=ti)

    assert branch == "reject_sales"
    assert ti.pushed["rows_rejected_pre_load"] == 2000
    assert "validated_batches" not in ti.pushed
