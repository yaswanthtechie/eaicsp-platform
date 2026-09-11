import hashlib
import math
from typing import Any, Dict

from src.experiment import ABExperiment


def deterministic_bucket(request_id: str) -> int:
    """
    Convert request ID into a deterministic bucket from 0 to 99.

    The same request ID always gets the same bucket.
    """

    if not isinstance(request_id, str):
        raise TypeError("request_id must be a string.")

    if not request_id:
        raise ValueError("request_id cannot be empty.")

    digest = hashlib.sha256(
        request_id.encode("utf-8")
    ).hexdigest()

    return int(digest[:8], 16) % 100


def assign_variant(
    request_id: str,
    experiment: ABExperiment,
) -> str:
    """
    Deterministically assign a request to variant A or B.

    traffic_percentage represents the percentage of traffic
    sent to variant B.
    """

    bucket = deterministic_bucket(request_id)

    if bucket < experiment.traffic_percentage:
        return experiment.variant_b

    return experiment.variant_a


class ABMetrics:
    """
    In-memory metrics for A/B experiment variants.
    """

    def __init__(self) -> None:
        self._metrics: Dict[str, Dict[str, Any]] = {}

    def _ensure_variant(self, variant: str) -> None:
        if variant not in self._metrics:
            self._metrics[variant] = {
                "requests": 0,
                "successes": 0,
                "failures": 0,
                "total_latency_ms": 0.0,
            }

    def record(
        self,
        variant: str,
        latency_ms: float,
        success: bool = True,
    ) -> None:

        self._ensure_variant(variant)

        metrics = self._metrics[variant]

        metrics["requests"] += 1
        metrics["total_latency_ms"] += float(latency_ms)

        if success:
            metrics["successes"] += 1
        else:
            metrics["failures"] += 1

    def summary(self) -> Dict[str, Dict[str, Any]]:
        result = {}

        for variant, metrics in self._metrics.items():

            requests = metrics["requests"]

            average_latency = (
                metrics["total_latency_ms"] / requests
                if requests
                else 0.0
            )

            success_rate = (
                metrics["successes"] / requests
                if requests
                else 0.0
            )

            result[variant] = {
                "requests": requests,
                "successes": metrics["successes"],
                "failures": metrics["failures"],
                "average_latency_ms": round(
                    average_latency,
                    3,
                ),
                "success_rate": round(
                    success_rate,
                    4,
                ),
            }

        return result
    


def _normal_cdf(value: float) -> float:
    """
    Standard normal cumulative distribution function.
    """

    return 0.5 * (
        1.0 + math.erf(value / math.sqrt(2.0))
    )


def compare_variants(
    metrics_a: Dict[str, Any],
    metrics_b: Dict[str, Any],
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """
    Compare two variants using a two-proportion z-test.

    The comparison uses success rate.

    Returns:
        p_value
        verdict
        winner
        loser
    """

    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1.")

    n_a = metrics_a["requests"]
    n_b = metrics_b["requests"]

    if n_a == 0 or n_b == 0:
        return {
            "p_value": None,
            "verdict": "inconclusive",
            "winner": None,
            "loser": None,
            "reason": "Both variants require at least one request.",
        }

    success_a = metrics_a["successes"]
    success_b = metrics_b["successes"]

    p_a = success_a / n_a
    p_b = success_b / n_b

    pooled = (success_a + success_b) / (n_a + n_b)

    standard_error = math.sqrt(
        pooled
        * (1 - pooled)
        * ((1 / n_a) + (1 / n_b))
    )

    if standard_error == 0:
        return {
            "p_value": 1.0,
            "verdict": "inconclusive",
            "winner": None,
            "loser": None,
            "reason": "No measurable difference between variants.",
        }

    z_score = (p_a - p_b) / standard_error

    p_value = 2 * (
        1 - _normal_cdf(abs(z_score))
    )

    if p_value < alpha:
        if p_a > p_b:
            winner = "variant_a"
            loser = "variant_b"
        else:
            winner = "variant_b"
            loser = "variant_a"

        verdict = "significant_difference"
    else:
        winner = None
        loser = None
        verdict = "inconclusive"

    return {
        "p_value": round(p_value, 6),
        "alpha": alpha,
        "verdict": verdict,
        "winner": winner,
        "loser": loser,
        "success_rate_a": round(p_a, 4),
        "success_rate_b": round(p_b, 4),
    }