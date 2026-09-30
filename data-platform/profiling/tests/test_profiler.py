import pandas as pd

from src.profiler import Profiler
from src.monitoring import MonitoringHistory
from src.audit_archive import AuditArchive

def test_empty_dataframe():
    df = pd.DataFrame()

    profiler = Profiler()
    report = profiler.profile(df)

    assert report is not None
    assert report["shape"] == [0, 0]
    assert report["columns"] == []


def test_all_null_column():
    df = pd.DataFrame({
        "quantity_sold": [None, None, None, None]
    })

    profiler = Profiler()
    report = profiler.profile(df)

    assert report["column_summary"][0]["null_count"] == 4
    assert report["column_summary"][0]["null_percent"] == 100.0


def test_wrong_dtype():
    df = pd.DataFrame({
        "quantity_sold": ["ten", "twenty", "thirty"]
    })

    profiler = Profiler()
    report = profiler.profile(df)

    assert report["column_summary"][0]["dtype"] in ("object", "str")

def test_profiler_discovers_relationships():
    left = pd.DataFrame({
        "sku_id": [f"SKU{i:03d}" for i in range(1, 12)]
    })

    right = pd.DataFrame({
        "product_code": [f"SKU{i:03d}" for i in range(1, 12)]
    })

    profiler = Profiler()

    result = profiler.discover_relationships(
        left,
        right
    )

    assert len(result) == 1
    assert result[0]["left_column"] == "sku_id"
    assert result[0]["right_column"] == "product_code"
    assert result[0]["overlap_percentage"] == 100.0
    assert result[0]["classification"] == "likely_join_key"

def test_profiler_monitor_keeps_all_audit_records(
    tmp_path,
    monkeypatch,
):
    history_file = tmp_path / "history.json"
    audit_file = tmp_path / "audit_archive.json"

    monkeypatch.setattr(
        "src.profiler.MonitoringHistory",
        lambda: MonitoringHistory(
            history_file=history_file
        ),
    )

    monkeypatch.setattr(
        "src.profiler.AuditArchive",
        lambda: AuditArchive(
            archive_file=audit_file
        ),
    )

    df = pd.DataFrame({
        "sku_id": ["SKU001", "SKU002", "SKU003"],
        "quantity_sold": [10, 20, 30],
        "unit_price": [100, 200, 300],
    })

    profiler = Profiler()

    first_result = profiler.monitor(df)
    second_result = profiler.monitor(df)

    archive = AuditArchive(
        archive_file=audit_file
    )

    records = archive.load_archive()

    assert len(records) == 2

    assert (
        records[0]["run_id"]
        == first_result["audit"]["run_id"]
    )

    assert (
        records[1]["run_id"]
        == second_result["audit"]["run_id"]
    )

    assert (
        records[0]["run_id"]
        != records[1]["run_id"]
    )

def test_profiler_can_query_audit_runs(
    tmp_path,
    monkeypatch,
):
    audit_file = tmp_path / "audit_archive.json"

    monkeypatch.setattr(
        "src.profiler.AuditArchive",
        lambda: AuditArchive(
            archive_file=audit_file
        ),
    )

    archive = AuditArchive(
        archive_file=audit_file
    )

    archive.save_run(
        {
            "quality_score": {
                "score": 90
            }
        }
    )

    archive.save_run(
        {
            "quality_score": {
                "score": 70
            }
        }
    )

    profiler = Profiler()

    results = profiler.query_audit_runs(
        min_quality_score=80
    )

    assert len(results) == 1
    assert (
        results[0]["profile_report"]["quality_score"]["score"]
        == 90
    )