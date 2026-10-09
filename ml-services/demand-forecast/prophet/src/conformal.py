"""Time-ordered split-conformal interval utilities."""

from __future__ import annotations

import math

import numpy as np


def _validate_coverage(coverage: float) -> None:
    if not 0.0 < coverage < 1.0:
        raise ValueError(
            f"coverage must be between 0 and 1, got {coverage}"
        )


def _validate_arrays(
    actual: np.ndarray,
    predicted: np.ndarray,
) -> None:
    if len(actual) != len(predicted):
        raise ValueError(
            "actual and predicted must have the same length."
        )

    if len(actual) == 0:
        raise ValueError(
            "actual and predicted cannot be empty."
        )

    if not np.all(np.isfinite(actual)):
        raise ValueError(
            "actual contains non-finite values."
        )

    if not np.all(np.isfinite(predicted)):
        raise ValueError(
            "predicted contains non-finite values."
        )


def relative_nonconformity_scores(
    actual,
    predicted,
    epsilon: float = 1e-8,
) -> np.ndarray:
    """
    Calculate relative absolute conformal scores.

    score = |actual - predicted| / max(|predicted|, epsilon)

    This keeps the interval scale-compatible with the existing
    multi-horizon ratio-based interval implementation.
    """

    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)

    _validate_arrays(actual, predicted)

    if epsilon <= 0:
        raise ValueError(
            f"epsilon must be positive, got {epsilon}"
        )

    denominator = np.maximum(
        np.abs(predicted),
        epsilon,
    )

    scores = np.abs(
        actual - predicted
    ) / denominator

    return scores

def calibration_radius(
    actual,
    predicted,
    coverage: float,
) -> float:
    """
    Calculate a split-conformal relative radius from
    a time-ordered calibration window.

    The calibration observations must come from a period
    strictly before the held-out evaluation period.
    """
    scores = relative_nonconformity_scores(
        actual,
        predicted,
    )

    return conformal_quantile(
        scores,
        coverage=coverage,
    )

def conformal_quantile(
    scores,
    coverage: float,
) -> float:
    """
    Return the finite-sample split-conformal quantile.

    For n calibration scores and target coverage C:

        k = ceil((n + 1) * C)

    The k-th smallest score is used. If k > n,
    the largest observed score is used.
    """

    _validate_coverage(coverage)

    scores = np.asarray(
        scores,
        dtype=float,
    )

    if len(scores) == 0:
        raise ValueError(
            "At least one calibration score is required."
        )

    if not np.all(np.isfinite(scores)):
        raise ValueError(
            "Conformal scores contain non-finite values."
        )

    if np.any(scores < 0):
        raise ValueError(
            "Conformal scores must be non-negative."
        )

    sorted_scores = np.sort(scores)

    rank = math.ceil(
        (len(sorted_scores) + 1) * coverage
    )

    rank = min(
        max(rank, 1),
        len(sorted_scores),
    )

    return float(
        sorted_scores[rank - 1]
    )


def build_relative_conformal_interval(
    predicted,
    radius: float,
):
    """
    Build a non-negative prediction interval from
    a relative conformal radius.

    lower = prediction * (1 - radius)
    upper = prediction * (1 + radius)
    """

    predicted = np.asarray(
        predicted,
        dtype=float,
    )

    if not np.all(np.isfinite(predicted)):
        raise ValueError(
            "predicted contains non-finite values."
        )

    if radius < 0 or not np.isfinite(radius):
        raise ValueError(
            f"radius must be finite and non-negative, got {radius}"
        )

    lower = np.maximum(
        0.0,
        predicted * (1.0 - radius),
    )

    upper = np.maximum(
        lower,
        predicted * (1.0 + radius),
    )

    return lower, upper


def interval_coverage(
    actual,
    lower,
    upper,
) -> float:
    """Return the fraction of actual values inside the interval."""

    actual = np.asarray(actual, dtype=float)
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)

    if not (
        len(actual)
        == len(lower)
        == len(upper)
    ):
        raise ValueError(
            "actual, lower and upper must have the same length."
        )

    if len(actual) == 0:
        raise ValueError(
            "Interval coverage requires at least one observation."
        )

    if not np.all(np.isfinite(actual)):
        raise ValueError(
            "actual contains non-finite values."
        )

    if not np.all(np.isfinite(lower)):
        raise ValueError(
            "lower contains non-finite values."
        )

    if not np.all(np.isfinite(upper)):
        raise ValueError(
            "upper contains non-finite values."
        )

    if np.any(lower > upper):
        raise ValueError(
            "lower interval bound cannot exceed upper bound."
        )

    inside = (
        (actual >= lower)
        & (actual <= upper)
    )

    return float(
        np.mean(inside)
    )


def pinball_loss(
    actual,
    predicted_quantile,
    quantile: float,
) -> float:
    """
    Calculate mean pinball loss for one quantile.
    """

    _validate_coverage(quantile)

    actual = np.asarray(
        actual,
        dtype=float,
    )

    predicted_quantile = np.asarray(
        predicted_quantile,
        dtype=float,
    )

    if len(actual) != len(predicted_quantile):
        raise ValueError(
            "actual and predicted_quantile must have "
            "the same length."
        )

    if len(actual) == 0:
        raise ValueError(
            "Pinball loss requires at least one observation."
        )

    if not np.all(np.isfinite(actual)):
        raise ValueError(
            "actual contains non-finite values."
        )

    if not np.all(
        np.isfinite(predicted_quantile)
    ):
        raise ValueError(
            "predicted_quantile contains non-finite values."
        )

    error = actual - predicted_quantile

    loss = np.maximum(
        quantile * error,
        (quantile - 1.0) * error,
    )

    return float(
        np.mean(loss)
    )


def interval_pinball_loss(
    actual,
    lower,
    upper,
    coverage: float,
) -> float:
    """
    Average pinball loss for the lower and upper
    bounds of a central prediction interval.

    Example:
        coverage=0.80
        lower quantile=0.10
        upper quantile=0.90
    """

    _validate_coverage(coverage)

    lower_quantile = (
        1.0 - coverage
    ) / 2.0

    upper_quantile = (
        1.0 + coverage
    ) / 2.0

    lower_loss = pinball_loss(
        actual,
        lower,
        lower_quantile,
    )

    upper_loss = pinball_loss(
        actual,
        upper,
        upper_quantile,
    )

    return float(
        (lower_loss + upper_loss) / 2.0
    )

def empirical_relative_interval(
    predicted,
    actual,
    coverage: float,
):
    """
    Build the existing empirical relative interval from
    calibration errors.

    This is the BEFORE baseline for comparison.
    """
    _validate_coverage(coverage)

    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)

    _validate_arrays(actual, predicted)

    denominator = np.maximum(
        np.abs(predicted),
        1e-8,
    )

    signed_error = (
        actual / denominator
    ) - 1.0

    lower_quantile = (1.0 - coverage) / 2.0
    upper_quantile = (1.0 + coverage) / 2.0

    low = float(
        np.quantile(
            signed_error,
            lower_quantile,
        )
    )

    high = float(
        np.quantile(
            signed_error,
            upper_quantile,
        )
    )

    return low, high
def evaluate_interval_methods(
    calibration_actual,
    calibration_predicted,
    evaluation_actual,
    evaluation_predicted,
    coverage: float,
) -> dict:
    """
    Compare the existing empirical interval against
    split-conformal interval on a held-out evaluation set.
    """

    calibration_actual = np.asarray(
        calibration_actual,
        dtype=float,
    )

    calibration_predicted = np.asarray(
        calibration_predicted,
        dtype=float,
    )

    evaluation_actual = np.asarray(
        evaluation_actual,
        dtype=float,
    )

    evaluation_predicted = np.asarray(
        evaluation_predicted,
        dtype=float,
    )

    # -----------------------------
    # BEFORE: empirical interval
    # -----------------------------
    low_multiplier, high_multiplier = (
        empirical_relative_interval(
            calibration_predicted,
            calibration_actual,
            coverage,
        )
    )

    before_lower = np.maximum(
        0.0,
        evaluation_predicted
        * (1.0 + low_multiplier),
    )

    before_upper = np.maximum(
        before_lower,
        evaluation_predicted
        * (1.0 + high_multiplier),
    )

    # -----------------------------
    # AFTER: conformal interval
    # -----------------------------
    radius = calibration_radius(
        calibration_actual,
        calibration_predicted,
        coverage,
    )

    after_lower, after_upper = (
        build_relative_conformal_interval(
            evaluation_predicted,
            radius,
        )
    )

    return {
        "coverage": coverage,
        "calibration_radius": radius,
        "before": {
            "coverage": interval_coverage(
                evaluation_actual,
                before_lower,
                before_upper,
            ),
            "pinball_loss": interval_pinball_loss(
                evaluation_actual,
                before_lower,
                before_upper,
                coverage,
            ),
        },
        "after": {
            "coverage": interval_coverage(
                evaluation_actual,
                after_lower,
                after_upper,
            ),
            "pinball_loss": interval_pinball_loss(
                evaluation_actual,
                after_lower,
                after_upper,
                coverage,
            ),
        },
    }