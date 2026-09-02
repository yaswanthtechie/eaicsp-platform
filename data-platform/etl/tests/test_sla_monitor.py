"""
R5 #2: Pipeline SLA monitoring - tests for the pure evaluate_sla() function.

check_run_duration_sla() (the DB-backed wrapper) is proven against a real
database via scripts/sla_monitoring_check.py, following the same
split-and-test pattern used for reconciliation.py.
"""

from etl.src.sla_monitor import evaluate_sla


def test_normal_run_within_sla_not_breached():
    # Usually ~120s, today 130s - unremarkable.
    result = evaluate_sla(
        current_duration_seconds=130,
        historical_durations_seconds=[120, 115, 125, 118, 122],
    )

    assert result["evaluable"] is True
    assert result["breached"] is False
    assert result["historical_avg_seconds"] == 120


def test_dramatically_slow_run_is_breached():
    # The spec's own example: usually 2 min, today 45 min.
    result = evaluate_sla(
        current_duration_seconds=45 * 60,
        historical_durations_seconds=[120, 118, 121, 119, 122],
    )

    assert result["evaluable"] is True
    assert result["breached"] is True
    assert result["historical_avg_seconds"] == 120


def test_run_exactly_at_threshold_is_not_breached():
    # threshold = avg * multiplier; strictly-greater-than semantics, so
    # landing exactly on the threshold doesn't trip a false alarm.
    result = evaluate_sla(
        current_duration_seconds=300,  # avg(100) * 3.0 == 300
        historical_durations_seconds=[100, 100, 100],
        threshold_multiplier=3.0,
    )

    assert result["evaluable"] is True
    assert result["breached"] is False


def test_insufficient_history_is_not_evaluable_and_never_breaches():
    # Only 2 prior runs, default min_historical_runs=3 - don't judge off
    # too little data, and definitely don't false-alarm on it.
    result = evaluate_sla(
        current_duration_seconds=99999,
        historical_durations_seconds=[100, 105],
    )

    assert result["evaluable"] is False
    assert result["breached"] is False
    assert result["historical_avg_seconds"] is None


def test_no_history_at_all_is_not_evaluable():
    result = evaluate_sla(
        current_duration_seconds=500,
        historical_durations_seconds=[],
    )

    assert result["evaluable"] is False
    assert result["breached"] is False


def test_custom_threshold_multiplier_is_respected():
    # A stricter 1.5x threshold catches what a 3x default would miss.
    result_strict = evaluate_sla(
        current_duration_seconds=200,
        historical_durations_seconds=[100, 100, 100],
        threshold_multiplier=1.5,
    )
    result_default = evaluate_sla(
        current_duration_seconds=200,
        historical_durations_seconds=[100, 100, 100],
        threshold_multiplier=3.0,
    )

    assert result_strict["breached"] is True
    assert result_default["breached"] is False
