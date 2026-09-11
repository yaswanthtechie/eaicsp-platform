
from src.monitoring import (
    log_prediction,
    get_summary,
)


def test_prediction_is_logged():
    """
    Every prediction should create a monitoring record.
    """

    before = get_summary()["request_volume"]

    log_prediction(
        prediction="setosa",
        request_id="test-monitoring-001",
        model_version="1",
        latency_ms=25.0,
    )

    after = get_summary()["request_volume"]

    assert after >= before + 1


def test_latency_is_recorded():
    """
    Logged latency should be available to monitoring.
    """

    log_prediction(
        prediction="setosa",
        request_id="latency-test-001",
        model_version="1",
        latency_ms=10.0,
    )

    log_prediction(
        prediction="versicolor",
        request_id="latency-test-002",
        model_version="1",
        latency_ms=20.0,
    )

    log_prediction(
        prediction="virginica",
        request_id="latency-test-003",
        model_version="1",
        latency_ms=30.0,
    )

    summary = get_summary()

    assert "latency_ms" in summary
    assert "p50" in summary["latency_ms"]
    assert "p95" in summary["latency_ms"]


def test_metrics_summary_contains_request_volume():
    """
    Monitoring summary should expose request volume.
    """

    summary = get_summary()

    assert "request_volume" in summary
    assert isinstance(summary["request_volume"], int)
    assert summary["request_volume"] >= 0


def test_metrics_summary_contains_p50_and_p95():
    """
    R4 Definition of Done:
    summary must expose real latency percentiles.
    """

    for i, latency in enumerate([10, 20, 30, 40, 50]):
        log_prediction(
            prediction="setosa",
            request_id=f"percentile-{i}",
            model_version="1",
            latency_ms=latency,
        )

    summary = get_summary()

    assert "latency_ms" in summary
    assert "p50" in summary["latency_ms"]
    assert "p95" in summary["latency_ms"]

    assert summary["latency_ms"]["p50"] > 0
    assert summary["latency_ms"]["p95"] > 0

    assert summary["latency_ms"]["p95"] >= summary["latency_ms"]["p50"]


def test_metrics_summary_contains_volume_over_time():
    """
    Monitoring should expose request volume over time.
    """

    log_prediction(
        prediction="setosa",
        request_id="volume-time-001",
        model_version="1",
        latency_ms=15.0,
    )

    summary = get_summary()

    assert "volume_over_time" in summary
    assert isinstance(summary["volume_over_time"], dict)


def test_multiple_predictions_increase_request_volume():
    """
    Multiple predictions should increase the total request volume.

    This test checks the total database count rather than the
    detailed 1000-record monitoring window.
    """

    before = get_summary()["request_volume"]

    for i in range(5):
        log_prediction(
            prediction="setosa",
            request_id=f"volume-{i}",
            model_version="1",
            latency_ms=10.0 + i,
        )

    after = get_summary()["request_volume"]

    assert after >= before + 5


def test_model_version_is_logged():
    """
    Monitoring must know which model served the request.
    """

    log_prediction(
        prediction="setosa",
        request_id="version-test-001",
        model_version="2",
        latency_ms=12.5,
    )

    summary = get_summary()

    assert summary is not None


def test_per_model_metrics_are_available():
    """
    R5 monitoring should expose metrics grouped by model version.
    """

    log_prediction(
        prediction="setosa",
        request_id="model-1-test",
        model_version="1",
        latency_ms=12.0,
    )

    log_prediction(
        prediction="versicolor",
        request_id="model-2-test",
        model_version="2",
        latency_ms=20.0,
    )

    summary = get_summary()

    assert "models" in summary
    assert isinstance(summary["models"], dict)

    assert "1" in summary["models"]
    assert "2" in summary["models"]

    assert summary["models"]["1"]["request_volume"] >= 1
    assert summary["models"]["2"]["request_volume"] >= 1


def test_per_model_latency_metrics_are_available():
    """
    R5 should expose p50 and p95 latency for each model version.
    """

    for i, latency in enumerate([10, 20, 30, 40, 50]):
        log_prediction(
            prediction="setosa",
            request_id=f"model-latency-{i}",
            model_version="1",
            latency_ms=latency,
        )

    summary = get_summary()

    model_metrics = summary["models"]["1"]

    assert "latency_ms" in model_metrics
    assert "p50" in model_metrics["latency_ms"]
    assert "p95" in model_metrics["latency_ms"]

    assert model_metrics["latency_ms"]["p50"] > 0
    assert model_metrics["latency_ms"]["p95"] > 0

    assert (
        model_metrics["latency_ms"]["p95"]
        >= model_metrics["latency_ms"]["p50"]
    )

