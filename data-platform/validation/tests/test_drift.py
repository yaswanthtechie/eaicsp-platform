import json
import pytest
import logging
from pathlib import Path
from src.drift import ReportComparator
from src.validator import DataValidator, ConfigRule, ValidationResult


@pytest.fixture
def mock_history_dir(tmp_path):
    """Creates an isolated temporary history directory."""
    d = tmp_path / ".history"
    d.mkdir()
    return d


@pytest.fixture
def comparator(mock_history_dir):
    """Provides a ReportComparator wired to the temporary history directory."""
    return ReportComparator(history_dir=str(mock_history_dir), rolling_n=3)


# --- METRIC CALCULATION TESTS ---

def test_get_rule_fail_rate_combined(comparator):
    """Ensures failures from both errors and warnings are accurately summed."""
    report = {
        "total_rows": 100,
        "errors": [{"rule": "r1", "count": 5}],
        "warnings": [{"rule": "r1", "count": 2}, {"rule": "r2", "count": 10}]
    }
    assert comparator._get_rule_fail_rate(report, "r1") == 0.07  # 7 / 100
    assert comparator._get_rule_fail_rate(report, "r2") == 0.10  # 10 / 100
    assert comparator._get_rule_fail_rate(report, "r3") == 0.0  # Not present


def test_get_rule_fail_rate_zero_rows(comparator):
    """Prevents zero division errors when calculating failure rates on empty batches."""
    assert comparator._get_rule_fail_rate({"total_rows": 0}, "r1") == 0.0


# --- HISTORY I/O TESTS ---

def test_load_history_success(comparator, mock_history_dir):
    """Verifies reports are successfully loaded up to the rolling_n limit."""
    (mock_history_dir / "report_1.json").write_text(json.dumps({"total_rows": 10}))
    (mock_history_dir / "report_2.json").write_text(json.dumps({"total_rows": 20}))

    hist = comparator._load_history()
    assert len(hist) == 2
    assert hist[0]["total_rows"] == 10


def test_load_history_invalid_json(comparator, mock_history_dir, caplog):
    """Verifies invalid JSON files are safely skipped without crashing."""
    (mock_history_dir / "report_1.json").write_text("NOT VALID JSON")
    hist = comparator._load_history()
    assert len(hist) == 0
    assert "Failed to load historical report" in caplog.text


def test_save_report_success(comparator, mock_history_dir):
    """Verifies a Pydantic ValidationResult is properly serialized to disk."""
    res = ValidationResult(passed=True, total_rows=50, total_rows_affected=0)
    comparator.save_report(res)

    files = list(mock_history_dir.glob("report_*.json"))
    assert len(files) == 1

    with open(files[0]) as f:
        data = json.load(f)
        assert data["total_rows"] == 50


def test_save_report_exception(comparator, monkeypatch, caplog):
    """Verifies save failures are caught and logged without touching the disk."""

    # Simulate a crash during Pydantic's JSON serialization
    def mock_dump_json(*args, **kwargs):
        raise ValueError("Simulated serialization crash")

    monkeypatch.setattr(ValidationResult, "model_dump_json", mock_dump_json)

    res = ValidationResult(passed=True, total_rows=50, total_rows_affected=0)
    comparator.save_report(res)

    assert "Failed to save validation history" in caplog.text


# --- DRIFT EVALUATION TESTS ---

def test_evaluate_drift_no_history(comparator):
    """Verifies behavior when evaluating the very first run in an environment."""
    rule = ConfigRule(**{"name": "r1", "field": "col", "type": "not_null"})
    val = DataValidator([rule])
    res = ValidationResult(passed=True, total_rows=100, total_rows_affected=0)

    alerts = comparator.evaluate_drift(res, val)
    assert alerts == []


def test_evaluate_drift_initialization(comparator, mock_history_dir, caplog):
    """Verifies baseline initialization logging for brand new rules lacking history."""
    caplog.set_level(logging.INFO)  # FIX: Tell pytest to capture INFO logs

    # Write a historical report with 0 rows (representing no history for the rule)
    (mock_history_dir / "report_1.json").write_text(json.dumps({"total_rows": 0}))

    rule = ConfigRule(**{"name": "r1", "field": "col", "type": "not_null"})
    val = DataValidator([rule])
    res = ValidationResult(passed=True, total_rows=100, total_rows_affected=0)

    alerts = comparator.evaluate_drift(res, val)
    assert alerts == []
    assert "Baseline initializing for rule 'r1'" in caplog.text


def test_evaluate_drift_triggers_alerts(comparator, mock_history_dir):
    """Verifies alerts trigger properly when BOTH abs and rel thresholds are breached."""
    # Baseline: 10 failures out of 100 = 10% rate
    (mock_history_dir / "report_1.json").write_text(json.dumps({
        "total_rows": 100,
        "errors": [{"rule": "r1", "count": 10}]
    }))

    rule = ConfigRule(**{"name": "r1", "field": "col", "type": "not_null"})
    val = DataValidator([rule], global_drift_abs_min=0.01, global_drift_rel_min=0.50)

    # Current: 20 failures out of 100 = 20% rate.
    # Absolute increase is 10 points (0.10) -> exceeds 0.01
    # Relative increase is 100% (1.00) -> exceeds 0.50
    res = ValidationResult(
        passed=False,
        total_rows=100,
        total_rows_affected=20,
        errors=[{"rule": "r1", "field": "col", "count": 20}]
    )

    alerts = comparator.evaluate_drift(res, val)
    assert len(alerts) == 1
    assert "Drift Alert (vs Last Run): Rule 'r1' failure rate jumped to 20.00%" in alerts[0]


def test_evaluate_drift_suppresses_below_threshold(comparator, mock_history_dir):
    """Verifies minor variance does not trigger false positive alerts."""
    # Baseline: 10 failures out of 100 = 10% rate
    (mock_history_dir / "report_1.json").write_text(json.dumps({
        "total_rows": 100,
        "errors": [{"rule": "r1", "count": 10}]
    }))

    rule = ConfigRule(**{"name": "r1", "field": "col", "type": "not_null"})
    val = DataValidator([rule], global_drift_abs_min=0.01, global_drift_rel_min=0.50)

    # Current: 11 failures out of 100 = 11% rate.
    # Absolute increase is 1 point (0.01). It is NOT strictly greater than 0.01.
    res = ValidationResult(
        passed=False,
        total_rows=100,
        total_rows_affected=11,
        errors=[{"rule": "r1", "field": "col", "count": 11}]
    )

    alerts = comparator.evaluate_drift(res, val)
    assert len(alerts) == 0


def test_evaluate_drift_skips_transform_rules(comparator, mock_history_dir):
    """Verifies transform rules, which do not produce failures, are ignored by the comparator."""
    (mock_history_dir / "report_1.json").write_text(json.dumps({"total_rows": 100}))

    # 'dummy' is not in SAFE_FUNCTION_REGISTRY, so mock it for this test just to instantiate
    rule = ConfigRule(**{"name": "t1", "type": "transform", "function": "src.custom_rules.flag_negatives"})
    val = DataValidator([rule])
    res = ValidationResult(passed=True, total_rows=100, total_rows_affected=0)

    alerts = comparator.evaluate_drift(res, val)
    assert len(alerts) == 0


def test_evaluate_drift_zero_baseline_jump(comparator, mock_history_dir):
    """Hits the branch where baseline is 0 but current failures jump > 0 (delta_rel = inf)."""
    (mock_history_dir / "report_1.json").write_text(json.dumps({
        "total_rows": 100,
        "errors": []
    }))
    rule = ConfigRule(**{"name": "r1", "field": "col", "type": "not_null"})
    val = DataValidator([rule], global_drift_abs_min=0.01, global_drift_rel_min=0.50)

    # 5% current failure rate jumps from a 0% baseline
    res = ValidationResult(passed=False, total_rows=100, total_rows_affected=5,
                           errors=[{"rule": "r1", "field": "col", "count": 5}])
    alerts = comparator.evaluate_drift(res, val)

    assert len(alerts) == 1
    assert "inf%" in alerts[0]


def test_evaluate_drift_zero_baseline_no_jump(comparator, mock_history_dir):
    """Hits the branch where baseline is 0 and current failures remain 0 (delta_rel = 0.0)."""
    (mock_history_dir / "report_1.json").write_text(json.dumps({
        "total_rows": 100,
        "errors": []
    }))
    rule = ConfigRule(**{"name": "r1", "field": "col", "type": "not_null"})
    val = DataValidator([rule], global_drift_abs_min=0.01, global_drift_rel_min=0.50)

    res = ValidationResult(passed=True, total_rows=100, total_rows_affected=0)
    alerts = comparator.evaluate_drift(res, val)
    assert len(alerts) == 0


def test_evaluate_drift_rolling_baseline(comparator, mock_history_dir):
    """Hits the `if len(history) > 1` branch to evaluate the rolling baseline."""
    # Baseline 1: 0 failures
    (mock_history_dir / "report_1.json").write_text(json.dumps({"total_rows": 100, "errors": []}))
    # Baseline 2: 10 failures
    (mock_history_dir / "report_2.json").write_text(
        json.dumps({"total_rows": 100, "errors": [{"rule": "r1", "count": 10}]}))

    rule = ConfigRule(**{"name": "r1", "field": "col", "type": "not_null"})
    val = DataValidator([rule], global_drift_abs_min=0.01, global_drift_rel_min=0.50)

    # Current: 20 failures
    res = ValidationResult(passed=False, total_rows=100, total_rows_affected=20,
                           errors=[{"rule": "r1", "field": "col", "count": 20}])
    alerts = comparator.evaluate_drift(res, val)

    assert len(alerts) == 2
    assert "vs Last Run" in alerts[0]
    assert "vs Rolling Avg (n=2)" in alerts[1]