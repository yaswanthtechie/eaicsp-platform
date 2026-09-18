from src.monitoring import MonitoringHistory


def create_batch(score):
    return {
        "quality_score": {
            "score": score,
            "missing_values": 0,
            "duplicate_rows": 0,
            "total_outliers": 0
        },
        "column_summary": []
    }


def test_compare_runs_increasing(tmp_path):
    history = MonitoringHistory(
        history_file=tmp_path / "history.json"
    )

    history.save_batch(create_batch(80))
    history.save_batch(create_batch(85))
    history.save_batch(create_batch(90))

    result = history.compare_runs("quality_score", last_n=3)

    assert result["runs"] == 3
    assert result["values"] == [80, 85, 90]
    assert result["change"] == 10
    assert result["trend"] == "Increasing"


def test_compare_runs_decreasing(tmp_path):
    history = MonitoringHistory(
        history_file=tmp_path / "history.json"
    )

    history.save_batch(create_batch(95))
    history.save_batch(create_batch(90))
    history.save_batch(create_batch(85))

    result = history.compare_runs("quality_score", last_n=3)

    assert result["values"] == [95, 90, 85]
    assert result["change"] == -10
    assert result["trend"] == "Decreasing"


def test_compare_runs_stable(tmp_path):
    history = MonitoringHistory(
        history_file=tmp_path / "history.json"
    )

    history.save_batch(create_batch(90))
    history.save_batch(create_batch(90))
    history.save_batch(create_batch(90))

    result = history.compare_runs("quality_score", last_n=3)

    assert result["values"] == [90, 90, 90]
    assert result["change"] == 0
    assert result["trend"] == "Stable"


def test_compare_runs_last_n(tmp_path):
    history = MonitoringHistory(
        history_file=tmp_path / "history.json"
    )

    history.save_batch(create_batch(70))
    history.save_batch(create_batch(75))
    history.save_batch(create_batch(80))
    history.save_batch(create_batch(85))

    result = history.compare_runs("quality_score", last_n=2)

    assert result["runs"] == 2
    assert result["values"] == [80, 85]
    assert result["change"] == 5


def test_compare_runs_no_data(tmp_path):
    history = MonitoringHistory(
        history_file=tmp_path / "history.json"
    )

    result = history.compare_runs("quality_score")

    assert result["runs"] == 0
    assert result["values"] == []
    assert result["trend"] == "No Data"


def test_compare_runs_not_enough_data(tmp_path):
    history = MonitoringHistory(
        history_file=tmp_path / "history.json"
    )

    history.save_batch(create_batch(90))

    result = history.compare_runs("quality_score")

    assert result["runs"] == 1
    assert result["values"] == [90]
    assert result["trend"] == "Not Enough Data"


def test_compare_runs_detects_gradual_degradation(tmp_path):
    history = MonitoringHistory(
        history_file=tmp_path / "history.json"
    )

    for score in [100, 99.5, 99.0, 98.5, 98.0, 97.5, 97.0, 96.5, 96.0, 95.5]:
        history.save_batch(create_batch(score))

    result = history.compare_runs(
        "quality_score",
        last_n=10
    )

    assert result["runs"] == 10
    assert result["trend"] == "Decreasing"
    assert result["slope"] < 0
    assert result["gradual_drift"] is True

def _save_scores(history, scores):
    for score in scores:
        history.save_batch(create_batch(score))


def test_compare_runs_detects_slow_drift_hidden_by_noise(tmp_path):
    """
    Loses ~0.5 points per run with noise. No single run-to-run change is
    bigger than 1.5 points, so run-vs-run comparison would not flag it.
    """
    history = MonitoringHistory(
        history_file=tmp_path / "history.json"
    )

    _save_scores(
        history,
        [95.0, 95.2, 93.9, 93.8, 93.2, 92.4, 92.3, 91.1, 91.0, 90.4]
    )

    result = history.compare_runs(
        "quality_score",
        last_n=10
    )

    assert result["slope"] < -0.3
    assert result["trend"] == "Decreasing"
    assert result["gradual_drift"] is True


def test_compare_runs_ignores_small_noise(tmp_path):
    history = MonitoringHistory(
        history_file=tmp_path / "history.json"
    )

    _save_scores(
        history,
        [95.0, 95.1, 94.9, 95.05, 94.95, 95.0, 95.1, 94.9, 94.95, 94.9]
    )

    result = history.compare_runs(
        "quality_score",
        last_n=10
    )

    assert result["trend"] == "Stable"
    assert result["gradual_drift"] is False


def test_compare_runs_needs_enough_runs_to_call_drift(tmp_path):
    history = MonitoringHistory(
        history_file=tmp_path / "history.json"
    )

    _save_scores(history, [90, 85, 80])

    result = history.compare_runs(
        "quality_score",
        last_n=3
    )

    assert result["trend"] == "Decreasing"
    assert result["gradual_drift"] is False