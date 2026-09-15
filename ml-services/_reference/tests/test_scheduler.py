from src.scheduler import RetrainingScheduler


def test_scheduler_run_once():

    calls = []

    def check():

        calls.append(True)

        return {
            "status": "retrained",
            "new_model_version": "4",
        }

    scheduler = RetrainingScheduler(
        check_function=check,
        interval_seconds=1,
    )

    result = scheduler.run_once()

    assert calls == [True]

    assert result["status"] == "retrained"

    assert result["new_model_version"] == "4"


def test_scheduler_does_not_retrain_without_drift():

    def check():

        return {
            "status": "skipped",
            "reason": "No significant drift detected",
        }

    scheduler = RetrainingScheduler(
        check_function=check,
        interval_seconds=1,
    )

    result = scheduler.run_once()

    assert result["status"] == "skipped"