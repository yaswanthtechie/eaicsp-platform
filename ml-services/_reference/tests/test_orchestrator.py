from src.orchestrator import (
    MultiModelRetrainingOrchestrator,
)


def make_model(
    *,
    drift: bool,
    candidate_score: float = 0.95,
    production_score: float = 0.90,
):
    state = {
        "version": "v1",
        "promoted": None,
        "retrained": False,
    }

    def get_version():
        return state["version"]

    def check_drift():
        return {
            "drift_detected": drift
        }

    def retrain():
        state["retrained"] = True

        return {
            "version": "v2",
            "score": candidate_score,
        }

    def evaluate_production():
        return production_score

    def promote(version):
        state["version"] = version
        state["promoted"] = version
        return version

    return {
        "get_version": get_version,
        "check_drift": check_drift,
        "retrain": retrain,
        "evaluate_production": evaluate_production,
        "promote": promote,
        "state": state,
    }


def test_no_drift_skips_retraining():
    model = make_model(drift=False)

    orchestrator = MultiModelRetrainingOrchestrator(
        {
            "forecast": {
                key: value
                for key, value in model.items()
                if key != "state"
            }
        }
    )

    result = orchestrator.run_model("forecast")

    assert result["status"] == "skipped"
    assert result["reason"] == "drift_not_detected"
    assert model["state"]["retrained"] is False


def test_drift_triggers_retraining_and_promotion():
    model = make_model(
        drift=True,
        candidate_score=0.95,
        production_score=0.90,
    )

    orchestrator = MultiModelRetrainingOrchestrator(
        {
            "forecast": {
                key: value
                for key, value in model.items()
                if key != "state"
            }
        }
    )

    result = orchestrator.run_model("forecast")

    assert result["status"] == "promoted"
    assert result["candidate_version"] == "v2"
    assert model["state"]["retrained"] is True
    assert model["state"]["promoted"] == "v2"


def test_worse_candidate_is_rejected():
    model = make_model(
        drift=True,
        candidate_score=0.70,
        production_score=0.90,
    )

    orchestrator = MultiModelRetrainingOrchestrator(
        {
            "forecast": {
                key: value
                for key, value in model.items()
                if key != "state"
            }
        }
    )

    result = orchestrator.run_model("forecast")

    assert result["status"] == "rejected"
    assert (
        result["reason"]
        == "candidate_worse_than_production"
    )

    assert model["state"]["retrained"] is True
    assert model["state"]["promoted"] is None


def test_all_models_are_checked():
    models = {}

    for model_name in (
        "forecast",
        "eta",
        "anomaly",
        "risk",
    ):
        model = make_model(drift=False)

        models[model_name] = {
            key: value
            for key, value in model.items()
            if key != "state"
        }

    orchestrator = MultiModelRetrainingOrchestrator(
        models
    )

    result = orchestrator.run_all()

    assert result["status"] == "completed"
    assert result["models_checked"] == 4
    assert result["models_retrained"] == 0
    assert result["models_promoted"] == 0

    assert set(result["results"]) == {
        "forecast",
        "eta",
        "anomaly",
        "risk",
    }


def test_one_model_failure_does_not_stop_other_models():
    good_model = make_model(drift=False)

    def failing_drift():
        raise RuntimeError("drift service unavailable")

    models = {
        "forecast": {
            key: value
            for key, value in good_model.items()
            if key != "state"
        },
        "eta": {
            "get_version": lambda: "v1",
            "check_drift": failing_drift,
            "retrain": lambda: {
                "version": "v2",
                "score": 0.95,
            },
            "evaluate_production": lambda: 0.90,
            "promote": lambda version: version,
        },
    }

    orchestrator = MultiModelRetrainingOrchestrator(
        models
    )

    result = orchestrator.run_all()

    assert result["models_checked"] == 2
    assert result["results"]["eta"]["status"] == "error"
    assert result["results"]["forecast"]["status"] == "skipped"