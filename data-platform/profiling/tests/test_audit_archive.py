from src.audit_archive import AuditArchive
from datetime import datetime


def test_save_run_creates_audit_record(tmp_path):
    archive_file = tmp_path / "audit_archive.json"

    archive = AuditArchive(
        archive_file=archive_file
    )

    report = {
        "shape": [100, 5],
        "quality_score": {
            "score": 90,
            "missing_values": 2,
            "duplicate_rows": 0,
            "total_outliers": 1,
        },
    }

    record = archive.save_run(report)

    assert record["run_id"]
    assert record["timestamp"]
    assert record["schema_version"] == "1.0"
    assert record["profile_report"] == report
    assert record["drift_report"] is None

    assert archive_file.exists()


def test_audit_archive_keeps_all_runs(tmp_path):
    archive_file = tmp_path / "audit_archive.json"

    archive = AuditArchive(
        archive_file=archive_file
    )

    first_report = {
        "quality_score": {
            "score": 90,
        }
    }

    second_report = {
        "quality_score": {
            "score": 80,
        }
    }

    first_record = archive.save_run(first_report)
    second_record = archive.save_run(second_report)

    history = archive.load_archive()

    assert len(history) == 2
    assert history[0]["run_id"] == first_record["run_id"]
    assert history[1]["run_id"] == second_record["run_id"]

def test_get_run_by_id(tmp_path):
    archive_file = tmp_path / "audit_archive.json"

    archive = AuditArchive(
        archive_file=archive_file
    )

    report = {
        "quality_score": {
            "score": 95,
        }
    }

    saved_record = archive.save_run(report)

    result = archive.get_run_by_id(
        saved_record["run_id"]
    )

    assert result is not None
    assert result["run_id"] == saved_record["run_id"]
    assert result["profile_report"] == report

def test_query_runs_by_quality_score(tmp_path):
    archive_file = tmp_path / "audit_archive.json"

    archive = AuditArchive(
        archive_file=archive_file
    )

    archive.save_run(
        {
            "quality_score": {
                "score": 95,
            }
        }
    )

    archive.save_run(
        {
            "quality_score": {
                "score": 75,
            }
        }
    )

    archive.save_run(
        {
            "quality_score": {
                "score": 85,
            }
        }
    )

    results = archive.query_runs(
        min_quality_score=80
    )

    assert len(results) == 2

    scores = [
        record["profile_report"]["quality_score"]["score"]
        for record in results
    ]

    assert scores == [95, 85]

def test_query_runs_by_drift_status(tmp_path):
    archive_file = tmp_path / "audit_archive.json"

    archive = AuditArchive(
        archive_file=archive_file
    )

    archive.save_run(
        {
            "quality_score": {
                "score": 90,
            }
        },
        drift={
            "status": "No Drift"
        },
    )

    archive.save_run(
        {
            "quality_score": {
                "score": 75,
            }
        },
        drift={
            "status": "Major Drift"
        },
    )

    archive.save_run(
        {
            "quality_score": {
                "score": 85,
            }
        },
        drift={
            "status": "Minor Drift"
        },
    )

    results = archive.query_runs(
        drift_status="Major Drift"
    )

    assert len(results) == 1
    assert (
        results[0]["drift_report"]["status"]
        == "Major Drift"
    )

def test_query_runs_by_time_range(tmp_path):
    archive_file = tmp_path / "audit_archive.json"

    archive = AuditArchive(
        archive_file=archive_file
    )

    first_record = archive.save_run(
        {
            "quality_score": {
                "score": 90,
            }
        }
    )

    second_record = archive.save_run(
        {
            "quality_score": {
                "score": 80,
            }
        }
    )

    first_time = datetime.fromisoformat(
        first_record["timestamp"]
    )

    second_time = datetime.fromisoformat(
        second_record["timestamp"]
    )

    results = archive.query_runs(
        start_time=first_time,
        end_time=second_time,
    )

    assert len(results) == 2
    assert results[0]["run_id"] == first_record["run_id"]
    assert results[1]["run_id"] == second_record["run_id"]

def test_audit_archive_keeps_more_than_ten_runs(tmp_path):
    archive_file = tmp_path / "audit_archive.json"

    archive = AuditArchive(
        archive_file=archive_file
    )

    for score in range(100, 88, -1):
        archive.save_run(
            {
                "quality_score": {
                    "score": score
                }
            }
        )

    records = archive.load_archive()

    assert len(records) == 12

    assert (
        records[0]["profile_report"]["quality_score"]["score"]
        == 100
    )

    assert (
        records[-1]["profile_report"]["quality_score"]["score"]
        == 89
    )