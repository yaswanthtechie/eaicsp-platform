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