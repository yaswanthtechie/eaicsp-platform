import json
from pathlib import Path

from src.executive_summary import _extract_profiling_signals
from src import executive_summary

# A real report produced by Tharun's validator (data-platform/validation):
#   python -m src.validate_cli --file tests/data/messy_sales_500.csv \
#       --output <this file> --config configs/sales_rules.yaml
# We only read the file; we never import or call the validator.
THARUN_REPORT = (
    Path(__file__).parent / "fixtures" / "validation_report_tharun.json"
)

def test_extract_profiling_signals():
    profiling_report = {
        "quality_score": {
            "score": 82,
            "missing_values": 147,
            "duplicate_rows": 10,
            "total_outliers": 50,
        },
        "worst_issues": [
            {
                "column": "quantity_sold",
                "severity": "High",
                "problems": "50 outliers",
            }
        ],
        "insights": [
            "quantity_sold contains significant outliers."
        ],
    }

    result = _extract_profiling_signals(
        profiling_report
    )

    assert result["quality_score"] == 82
    assert result["missing_values"] == 147
    assert result["duplicate_rows"] == 10
    assert result["total_outliers"] == 50

    assert len(result["worst_issues"]) == 1
    assert len(result["insights"]) == 1

from src.executive_summary import (
    _extract_profiling_signals,
    _build_profiling_summary,
)


def test_build_profiling_summary():
    signals = {
        "quality_score": 82,
        "missing_values": 147,
        "duplicate_rows": 10,
        "total_outliers": 50,
        "worst_issues": [],
        "insights": [],
    }

    summary = _build_profiling_summary(
        signals
    )

    assert "82/100" in summary
    assert "147 missing values" in summary
    assert "10 duplicate rows" in summary
    assert "50 detected outliers" in summary

def test_extract_etl_signals():
    etl_output = {
        "status": "warning",
        "warnings": 2,
        "errors": 1,
        "sla_status": "met",
    }

    signals = executive_summary._extract_etl_signals(etl_output)

    assert signals["status"] == "warning"
    assert signals["warnings"] == 2
    assert signals["errors"] == 1
    assert signals["sla_status"] == "met"


def test_extract_validation_signals():
    validation_output = {
        "status": "fail",
        "invalid_rows": 12,
        "validation_failures": 3,
        "errors": 1,
        "warnings": 2,
    }

    signals = executive_summary._extract_validation_signals(validation_output)

    assert signals["status"] == "fail"
    assert signals["invalid_rows"] == 12
    assert signals["validation_failures"] == 3
    assert signals["errors"] == 1
    assert signals["warnings"] == 2

def test_build_etl_summary():
    signals = {
        "status": "warning",
        "warnings": 2,
        "errors": 1,
        "sla_status": "met",
    }

    summary = executive_summary._build_etl_summary(signals)

    assert "The ETL pipeline status is warning" in summary
    assert "SLA status is met" in summary
    assert "2 ETL warnings" in summary
    assert "1 ETL error" in summary

def test_build_validation_summary():
    signals = {
        "status": "fail",
        "invalid_rows": 12,
        "validation_failures": 3,
        "errors": 1,
        "warnings": 2,
    }

    summary = executive_summary._build_validation_summary(signals)

    assert "Validation status is fail" in summary
    assert "12 rows are invalid" in summary
    assert "3 validation failures" in summary
    assert "1 validation error" in summary
    assert "2 validation warnings" in summary

def test_generate_executive_summary():
    profiling_report = {
        "quality_score": {
            "score": 82
        },
        "missing_values": 10,
        "duplicate_rows": 2,
        "total_outliers": 3,
    }

    etl_output = {
        "status": "success",
        "warnings": 1,
        "errors": 0,
        "sla_status": "met",
    }

    validation_output = {
        "status": "pass",
        "invalid_rows": 0,
        "validation_failures": 0,
        "errors": 0,
        "warnings": 1,
    }

    summary = executive_summary.generate_executive_summary(
        profiling_report=profiling_report,
        etl_output=etl_output,
        validation_output=validation_output,
    )

    assert isinstance(summary, str)
    assert "quality score" in summary
    assert "The ETL pipeline status" in summary
    assert "Validation status" in summary

def test_generate_executive_summary_with_only_profiling():
    profiling_report = {
        "quality_score": {
            "score": 95
        },
        "missing_values": 0,
        "duplicate_rows": 0,
        "total_outliers": 0,
    }

    summary = executive_summary.generate_executive_summary(
        profiling_report=profiling_report
    )

    assert isinstance(summary, str)
    assert summary != ""
    assert "quality score" in summary

def test_generate_executive_summary_without_optional_outputs():
    profiling_report = {
        "quality_score": {
            "score": 90
        },
        "missing_values": 0,
        "duplicate_rows": 0,
        "total_outliers": 0,
    }

    summary = executive_summary.generate_executive_summary(
        profiling_report=profiling_report,
        etl_output=None,
        validation_output=None,
    )

    assert isinstance(summary, str)
    assert summary != ""
    assert "quality score" in summary
    assert "ETL" not in summary
    assert "validation" not in summary

def test_load_static_output_from_dict():
    data = {
        "status": "success",
        "warnings": 1,
    }

    result = executive_summary._load_static_output(data)

    assert result == data


def test_load_static_output_from_json_file(tmp_path):
    output_file = tmp_path / "etl_output.json"

    output_file.write_text(
        '{"status": "success", "warnings": 1}',
        encoding="utf-8",
    )

    result = executive_summary._load_static_output(output_file)

    assert result["status"] == "success"
    assert result["warnings"] == 1

def test_generate_executive_summary_from_json_files(tmp_path):
    etl_file = tmp_path / "etl_output.json"
    validation_file = tmp_path / "validation_output.json"

    etl_file.write_text(
        '{"status": "success", "warnings": 2, "errors": 0, "sla_status": "met"}',
        encoding="utf-8",
    )

    validation_file.write_text(
        '{"status": "pass", "invalid_rows": 3, "validation_failures": 1, "errors": 0, "warnings": 1}',
        encoding="utf-8",
    )

    profiling_report = {
        "quality_score": {
            "score": 85,
            "missing_values": 4,
            "duplicate_rows": 0,
            "total_outliers": 2,
        }
    }

    summary = executive_summary.generate_executive_summary(
        profiling_report=profiling_report,
        etl_output=etl_file,
        validation_output=validation_file,
    )

    assert "quality score" in summary
    assert "The ETL pipeline status is success" in summary
    assert "It reported 2 ETL warnings" in summary
    assert "Validation status is pass" in summary
    assert "3 rows are invalid" in summary

def test_load_static_output_missing_file():
    missing_file = "reports/does_not_exist.json"

    try:
        executive_summary._load_static_output(missing_file)
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError as exc:
        assert "Static output file not found" in str(exc)

def test_real_validation_report_is_summarised_correctly():
    """
    Tharun's real report says validation FAILED. The summary must say so,
    give counts (not raw lists), and name the worst rules.
    """
    report = json.loads(THARUN_REPORT.read_text(encoding="utf-8"))
    assert report["passed"] is False  # the fixture is a real failure

    summary = executive_summary.generate_executive_summary(
        profiling_report={"quality_score": {"score": 70}},
        validation_output=THARUN_REPORT,
    )

    assert "Validation status is fail" in summary
    assert f"{report['total_rows_affected']} rows are invalid" in summary
    assert f"It reported {len(report['errors'])} validation errors" in summary
    assert f"It reported {len(report['warnings'])} validation warnings" in summary

    worst_rule = max(report["errors"], key=lambda issue: issue["count"])
    assert "The most frequent validation errors were" in summary
    assert f"{worst_rule['rule']} ({worst_rule['count']} rows)" in summary

    # Never dump raw Python lists/dicts into an executive paragraph.
    assert "[" not in summary and "{" not in summary


def test_passed_real_validation_report_says_pass():
    summary = executive_summary.generate_executive_summary(
        profiling_report={"quality_score": {"score": 95}},
        validation_output={
            "passed": True,
            "total_rows_affected": 0,
            "errors": [],
            "warnings": [],
        },
    )

    assert "Validation status is pass" in summary
    assert "rows are invalid" not in summary


def test_rejected_batch_and_sla_breach_are_reported():
    summary = executive_summary.generate_executive_summary(
        profiling_report={"quality_score": {"score": 40}},
        validation_output={
            "passed": False,
            "total_rows_affected": 900,
            "errors": [{"rule": "not_null", "field": "sku_id", "count": 900}],
            "warnings": [],
            "batch_rejected": True,
            "sla_breached": True,
        },
    )

    assert "The validated batch was rejected" in summary
    assert "The validation SLA was breached" in summary


def test_list_valued_etl_counts_are_counted_not_printed():
    summary = executive_summary.generate_executive_summary(
        profiling_report={"quality_score": {"score": 90}},
        etl_output={
            "status": "success",
            "warnings": [{"message": "slow batch"}, {"message": "late file"}],
            "errors": [],
        },
    )

    assert "It reported 2 ETL warnings" in summary
    assert "[" not in summary and "{" not in summary