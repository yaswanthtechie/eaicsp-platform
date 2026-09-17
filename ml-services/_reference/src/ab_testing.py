
"""
A/B testing utilities for the unified multi-model serving platform.

Responsibilities:
- Deterministic request-to-variant assignment
- Per-variant runtime metrics
- Per-variant model quality metrics
- Statistical comparison between variants
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any, Dict, Mapping

from src.experiment import ABExperiment


def deterministic_bucket(request_id: str) -> int:
    """Return a stable bucket from 0 to 99 for a request ID."""
    if not isinstance(request_id, str):
        raise ValueError("request_id must be a string.")

    request_id = request_id.strip()

    if not request_id:
        raise ValueError("request_id must not be empty.")

    digest = hashlib.sha256(
        request_id.encode("utf-8")
    ).hexdigest()

    return int(digest[:8], 16) % 100


def assign_variant(
    request_id: str,
    experiment: ABExperiment,
) -> str:
    """Deterministically assign a request to variant A or B."""
    if not isinstance(experiment, ABExperiment):
        raise TypeError(
            "experiment must be an ABExperiment instance."
        )

    bucket = deterministic_bucket(request_id)

    if bucket < experiment.traffic_percentage:
        return experiment.variant_b

    return experiment.variant_a


@dataclass
class VariantMetrics:
    """Runtime and model-quality metrics for one A/B variant."""

    requests: int = 0
    successes: int = 0
    failures: int = 0

    total_latency_ms: float = 0.0

    quality_sum: float = 0.0
    quality_count: int = 0

    quality_scores: list[float] | None = None

    def __post_init__(self) -> None:
        if self.quality_scores is None:
            self.quality_scores = []


class ABMetrics:
    """Collect metrics independently for each A/B variant."""

    def __init__(self) -> None:
        self._metrics: Dict[str, VariantMetrics] = {}

    def _ensure_variant(self, variant: str) -> VariantMetrics:
        """Create metrics storage for a variant if required."""
        if not isinstance(variant, str):
            raise ValueError("variant must be a string.")

        variant = variant.strip()

        if not variant:
            raise ValueError("variant must not be empty.")

        if variant not in self._metrics:
            self._metrics[variant] = VariantMetrics()

        return self._metrics[variant]

    def record(
        self,
        variant: str,
        latency_ms: float,
        success: bool = True,
        quality_score: float | None = None,
    ) -> None:
        """
        Record one request.

        quality_score is an actual model-quality observation between
        0 and 1. It is kept separately from request success/failure.
        """
        try:
            latency_ms = float(latency_ms)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "latency_ms must be numeric."
            ) from exc

        if not math.isfinite(latency_ms):
            raise ValueError(
                "latency_ms must be finite."
            )

        if latency_ms < 0:
            raise ValueError(
                "latency_ms must be non-negative."
            )

        metrics = self._ensure_variant(variant)

        metrics.requests += 1
        metrics.total_latency_ms += latency_ms

        if success:
            metrics.successes += 1
        else:
            metrics.failures += 1

        if quality_score is not None:
            try:
                quality_score = float(quality_score)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "quality_score must be numeric."
                ) from exc

            if not math.isfinite(quality_score):
                raise ValueError(
                    "quality_score must be finite."
                )

            if not 0.0 <= quality_score <= 1.0:
                raise ValueError(
                    "quality_score must be between 0 and 1."
                )

            metrics.quality_sum += quality_score
            metrics.quality_count += 1

            metrics.quality_scores.append(
                quality_score
            )

    def summary(self) -> Dict[str, Dict[str, Any]]:
        """Return per-variant metrics."""
        result: Dict[str, Dict[str, Any]] = {}

        for variant, metrics in self._metrics.items():

            average_latency_ms = (
                metrics.total_latency_ms / metrics.requests
                if metrics.requests
                else 0.0
            )

            success_rate = (
                metrics.successes / metrics.requests
                if metrics.requests
                else 0.0
            )

            average_quality = (
                metrics.quality_sum / metrics.quality_count
                if metrics.quality_count
                else None
            )

            result[variant] = {
                "requests": metrics.requests,
                "successes": metrics.successes,
                "failures": metrics.failures,
                "average_latency_ms": round(
                    average_latency_ms,
                    4,
                ),
                "success_rate": round(
                    success_rate,
                    6,
                ),
                "quality_count": metrics.quality_count,
                "average_quality": (
                    round(average_quality, 6)
                    if average_quality is not None
                    else None
                ),
                # Backward-compatible field name.
                "average_quality_score": (
                    round(average_quality, 6)
                    if average_quality is not None
                    else None
                ),
                "quality_scores": list(
                    metrics.quality_scores
                ),
            }

        return result


def _normal_cdf(value: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (
        1.0 + math.erf(
            value / math.sqrt(2.0)
        )
    )


def _two_sided_p_value(z_score: float) -> float:
    """Return a two-sided normal-test p-value."""
    return 2.0 * (
        1.0 - _normal_cdf(
            abs(z_score)
        )
    )


def _extract_quality_scores(
    metrics: Mapping[str, Any],
) -> list[float]:
    """
    Extract actual quality observations.

    Preferred input:
        quality_scores=[...]

    Backward-compatible input:
        average_quality + quality_count
    """
    raw_scores = metrics.get("quality_scores")

    if raw_scores is not None:
        try:
            scores = [
                float(score)
                for score in raw_scores
            ]
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "quality_scores must contain numeric values."
            ) from exc

        for score in scores:
            if not math.isfinite(score):
                raise ValueError(
                    "quality_scores must contain finite values."
                )

            if not 0.0 <= score <= 1.0:
                raise ValueError(
                    "quality_scores must contain values between 0 and 1."
                )

        return scores

    quality_count = int(
        metrics.get("quality_count", 0)
    )

    average_quality = metrics.get(
        "average_quality"
    )

    if average_quality is None:
        average_quality = metrics.get(
            "average_quality_score"
        )

    if (
        quality_count <= 0
        or average_quality is None
    ):
        return []

    average_quality = float(
        average_quality
    )

    if not 0.0 <= average_quality <= 1.0:
        raise ValueError(
            "average_quality must be between 0 and 1."
        )

    return [average_quality] * quality_count


def compare_variants(
    metrics_a: Mapping[str, Any],
    metrics_b: Mapping[str, Any],
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """
    Statistically compare actual model-quality observations.

    A two-sample normal approximation is used on the observed
    quality-score means and sample variances.

    Higher quality is considered better.

    When both variants have zero observed variance, the result
    is handled explicitly:

    - identical deterministic means -> no_difference
    - different deterministic means -> significant_difference
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError(
            "alpha must be between 0 and 1."
        )

    scores_a = _extract_quality_scores(
        metrics_a
    )

    scores_b = _extract_quality_scores(
        metrics_b
    )

    if not scores_a or not scores_b:
        quality_a = metrics_a.get(
            "average_quality"
        )

        if quality_a is None:
            quality_a = metrics_a.get(
                "average_quality_score"
            )

        quality_b = metrics_b.get(
            "average_quality"
        )

        if quality_b is None:
            quality_b = metrics_b.get(
                "average_quality_score"
            )

        return {
            "p_value": None,
            "alpha": alpha,
            "verdict": "inconclusive",
            "winner": None,
            "loser": None,
            "quality_a": quality_a,
            "quality_b": quality_b,
            "reason": (
                "Both variants require model-quality "
                "observations before statistical comparison."
            ),
        }

    n_a = len(scores_a)
    n_b = len(scores_b)

    mean_a = sum(scores_a) / n_a
    mean_b = sum(scores_b) / n_b

    difference = mean_a - mean_b

    def sample_variance(
        values: list[float],
        mean: float,
    ) -> float:
        """Calculate sample variance."""
        if len(values) <= 1:
            return 0.0

        return sum(
            (value - mean) ** 2
            for value in values
        ) / (len(values) - 1)

    variance_a = sample_variance(
        scores_a,
        mean_a,
    )

    variance_b = sample_variance(
        scores_b,
        mean_b,
    )

    base_result = {
        "alpha": alpha,
        "quality_a": round(
            mean_a,
            6,
        ),
        "quality_b": round(
            mean_b,
            6,
        ),
        "difference": round(
            difference,
            6,
        ),
        "sample_count_a": n_a,
        "sample_count_b": n_b,
    }

    # ------------------------------------------------------------------
    # Problem 4 fix:
    #
    # When both variants have zero variance, the normal approximation
    # cannot calculate a normal z-score because the standard error is
    # zero.
    #
    # Identical deterministic scores:
    #     no_difference
    #
    # Different deterministic scores:
    #     significant_difference
    #
    # There is intentionally NO 0.01 threshold.
    # ------------------------------------------------------------------
    if variance_a == 0.0 and variance_b == 0.0:

        if mean_a == mean_b:
            return {
                **base_result,
                "p_value": 1.0,
                "verdict": "no_difference",
                "winner": None,
                "loser": None,
                "reason": (
                    "Both variants produced identical quality scores."
                ),
            }

        winner = (
            "variant_b"
            if mean_b > mean_a
            else "variant_a"
        )

        loser = (
            "variant_a"
            if winner == "variant_b"
            else "variant_b"
        )

        return {
            **base_result,
            "p_value": 0.0,
            "verdict": "significant_difference",
            "winner": winner,
            "loser": loser,
            "reason": (
                "Deterministic quality scores differ between variants."
            ),
        }

    # ------------------------------------------------------------------
    # Normal approximation for variants with observed variance.
    # ------------------------------------------------------------------
    standard_error = math.sqrt(
        (variance_a / n_a)
        + (variance_b / n_b)
    )

    if standard_error == 0.0:
        p_value = 1.0
    else:
        z_score = (
            difference / standard_error
        )

        p_value = _two_sided_p_value(
            z_score
        )

    if p_value < alpha:

        if mean_a > mean_b:
            winner = "variant_a"
            loser = "variant_b"

        elif mean_b > mean_a:
            winner = "variant_b"
            loser = "variant_a"

        else:
            winner = None
            loser = None

        verdict = (
            "significant_difference"
            if winner is not None
            else "inconclusive"
        )

    else:
        winner = None
        loser = None
        verdict = "inconclusive"

    return {
        "p_value": round(
            p_value,
            8,
        ),
        "alpha": alpha,
        "verdict": verdict,
        "winner": winner,
        "loser": loser,
        "quality_a": round(
            mean_a,
            6,
        ),
        "quality_b": round(
            mean_b,
            6,
        ),
        "difference": round(
            difference,
            6,
        ),
        "sample_count_a": n_a,
        "sample_count_b": n_b,
        "reason": (
            "Statistical comparison of observed "
            "model-quality scores."
        ),
    }

