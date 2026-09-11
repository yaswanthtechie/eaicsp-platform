from src.ab_testing import (
    ABMetrics,
    assign_variant,
    compare_variants,
    deterministic_bucket,
)
from src.experiment import ABExperiment


def test_deterministic_bucket_is_stable():
    request_id = "request-001"

    bucket1 = deterministic_bucket(request_id)
    bucket2 = deterministic_bucket(request_id)

    assert bucket1 == bucket2
    assert 0 <= bucket1 <= 99


def test_same_request_gets_same_variant():
    experiment = ABExperiment(
        model_name="forecast",
        variant_a="v1",
        variant_b="v2",
        traffic_percentage=50,
    )

    results = [
        assign_variant(
            "same-request",
            experiment,
        )
        for _ in range(20)
    ]

    assert len(set(results)) == 1


def test_only_configured_variants_are_returned():
    experiment = ABExperiment(
        model_name="forecast",
        variant_a="v1",
        variant_b="v2",
        traffic_percentage=50,
    )

    for i in range(1000):
        result = assign_variant(
            f"request-{i}",
            experiment,
        )

        assert result in {"v1", "v2"}


def test_50_50_split():
    experiment = ABExperiment(
        model_name="forecast",
        variant_a="v1",
        variant_b="v2",
        traffic_percentage=50,
    )

    variant_a_count = 0
    variant_b_count = 0

    total = 10000

    for i in range(total):
        result = assign_variant(
            f"request-{i}",
            experiment,
        )

        if result == "v1":
            variant_a_count += 1
        else:
            variant_b_count += 1

    ratio_a = variant_a_count / total
    ratio_b = variant_b_count / total

    assert 0.47 <= ratio_a <= 0.53
    assert 0.47 <= ratio_b <= 0.53


def test_metrics_are_separated_by_variant():
    metrics = ABMetrics()

    metrics.record(
        variant="v1",
        latency_ms=10,
        success=True,
    )

    metrics.record(
        variant="v1",
        latency_ms=20,
        success=False,
    )

    metrics.record(
        variant="v2",
        latency_ms=30,
        success=True,
    )

    summary = metrics.summary()

    assert summary["v1"]["requests"] == 2
    assert summary["v1"]["successes"] == 1
    assert summary["v1"]["failures"] == 1

    assert summary["v2"]["requests"] == 1
    assert summary["v2"]["successes"] == 1
    assert summary["v2"]["failures"] == 0


def test_statistical_difference_detected():
    metrics_a = {
        "requests": 1000,
        "successes": 950,
        "failures": 50,
    }

    metrics_b = {
        "requests": 1000,
        "successes": 800,
        "failures": 200,
    }

    result = compare_variants(
        metrics_a,
        metrics_b,
    )

    assert result["verdict"] == "significant_difference"
    assert result["winner"] == "variant_a"
    assert result["loser"] == "variant_b"
    assert result["p_value"] < 0.05


def test_statistical_comparison_is_inconclusive():
    metrics_a = {
        "requests": 1000,
        "successes": 900,
        "failures": 100,
    }

    metrics_b = {
        "requests": 1000,
        "successes": 901,
        "failures": 99,
    }

    result = compare_variants(
        metrics_a,
        metrics_b,
    )

    assert result["verdict"] == "inconclusive"
    assert result["winner"] is None
    assert result["loser"] is None