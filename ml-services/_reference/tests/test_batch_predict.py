from src.batch_predict import BatchPredictionService


class FakeModelManager:

    def predict(self, model_name, payload):
        return {
            "model": model_name,
            "features": payload,
        }


def test_batch_prediction():
    service = BatchPredictionService(
        model_manager=FakeModelManager()
    )

    result = service.predict(
        [
            {
                "model_name": "forecast",
                "features": {"value": 10},
            },
            {
                "model_name": "eta",
                "features": {"value": 20},
            },
        ]
    )

    assert result["summary"]["batch_size"] == 2
    assert result["summary"]["successful_predictions"] == 2
    assert result["summary"]["failed_predictions"] == 0
    assert result["summary"]["model_count"] == 2
    assert len(result["results"]) == 2


def test_empty_batch_rejected():
    service = BatchPredictionService(
        model_manager=FakeModelManager()
    )

    try:
        service.predict([])
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "cannot be empty" in str(exc)


def test_failed_model_does_not_break_entire_batch():

    class FailingModelManager:

        def predict(self, model_name, payload):
            if model_name == "bad_model":
                raise RuntimeError("model unavailable")

            return 123

    service = BatchPredictionService(
        model_manager=FailingModelManager()
    )

    result = service.predict(
        [
            {
                "model_name": "forecast",
                "features": {"value": 10},
            },
            {
                "model_name": "bad_model",
                "features": {"value": 20},
            },
        ]
    )

    assert result["summary"]["batch_size"] == 2
    assert result["summary"]["successful_predictions"] == 1
    assert result["summary"]["failed_predictions"] == 1

    assert result["results"][0]["success"] is True
    assert result["results"][1]["success"] is False
    assert "model unavailable" in result["results"][1]["error"]


def test_resource_metrics_are_recorded():

    service = BatchPredictionService(
        model_manager=FakeModelManager()
    )

    result = service.predict(
        [
            {
                "model_name": "forecast",
                "features": {"value": 10},
            }
        ]
    )

    metrics = result["resource_metrics"]

    assert metrics["batch_size"] == 1
    assert metrics["model_count"] == 1
    assert metrics["total_predictions"] == 1
    assert metrics["latency_ms"] >= 0
    assert metrics["memory_mb"] > 0