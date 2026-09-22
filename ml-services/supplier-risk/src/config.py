"""
Configuration module for the Supplier Risk ML Service.

Provides centralized, configurable parameters for sentiment penalties,
keyword signal weights, and scoring thresholds. Follows standard project
configuration conventions and supports environment variable overrides.
"""

import json
import os
from functools import lru_cache
from typing import Any, Dict, Final, Optional, Set


# ------------------------------------------------------------------
# Model Configuration
# ------------------------------------------------------------------

MODEL_NAME: str = os.getenv(
    "SUPPLIER_RISK_MODEL_NAME",
    "ProsusAI/finbert",
)


# ------------------------------------------------------------------
# Default Scoring Weights & Thresholds
# ------------------------------------------------------------------

DEFAULT_NEGATIVE_SENTIMENT_PENALTY: Final[float] = 40.0
DEFAULT_NEUTRAL_SENTIMENT_PENALTY: Final[float] = 0.0
DEFAULT_POSITIVE_SENTIMENT_PENALTY: Final[float] = 0.0
DEFAULT_MAX_RISK_SCORE: Final[float] = 100.0
DEFAULT_CONFIDENCE_DIVISOR: Final[float] = 8.0
DEFAULT_AGGREGATION_STRATEGY: Final[str] = "top_k_mean"
DEFAULT_AGGREGATION_TOP_K: Final[int] = 3
DEFAULT_RECENCY_HALF_LIFE_DAYS: Final[float] = 30.0
DEFAULT_TREND_WINDOW_DAYS: Final[int] = 30
DEFAULT_TREND_DIRECTION_THRESHOLD: Final[float] = 3.0
DEFAULT_VOLUME_WEIGHT: Final[float] = 0.15
DEFAULT_MITIGATION_WEIGHT: Final[float] = 0.35

# ------------------------------------------------------------------
# Fixed Risk Tier Classification Thresholds
# (Configured a priori before evaluation; independent of model prediction scores)
# ------------------------------------------------------------------

DEFAULT_TIER_LOW_CEILING: Final[float] = 60.0
DEFAULT_TIER_MEDIUM_CEILING: Final[float] = 72.0
DEFAULT_TIER_HIGH_CEILING: Final[float] = 85.0

TIER_BOUNDARIES: Final[Dict[str, float]] = {
    "Low": DEFAULT_TIER_LOW_CEILING,
    "Medium": DEFAULT_TIER_MEDIUM_CEILING,
    "High": DEFAULT_TIER_HIGH_CEILING,
}


ALLOWED_AGGREGATION_STRATEGIES: Final[Set[str]] = {
    "top_k_mean",
    "max",
    "blend",
    "mean",
}

DEFAULT_SIGNAL_WEIGHTS: Final[Dict[str, int]] = {
    # Financial Risks
    "bankruptcy": 50,
    "insolvency": 45,
    "default": 40,
    "restructuring": 20,
    "layoff": 25,
    "downgrade": 20,

    # Operational Risks
    "strike": 25,
    "recall": 30,
    "disruption": 20,
    "shortage": 20,
    "delays": 15,
    "shutdown": 35,
    "outage": 25,

    # Reputational / Security Risks
    "fraud": 40,
    "investigation": 25,
    "lawsuit": 25,
    "sanction": 35,
    "cyberattack": 35,
}


# ------------------------------------------------------------------
# Validation Utilities
# ------------------------------------------------------------------

def validate_numeric_weight(name: str, value: Any, allow_zero: bool = True) -> float:
    """
    Validate that a weight value is numeric and non-negative.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"Weight '{name}' must be numeric, got {type(value).__name__}: {value}")
    if value < 0:
        raise ValueError(f"Weight '{name}' cannot be negative, got {value}")
    if not allow_zero and value == 0:
        raise ValueError(f"Weight '{name}' must be greater than zero, got {value}")
    return float(value)


def validate_signal_weights(weights: Dict[str, Any]) -> Dict[str, int]:
    """
    Validate a dictionary of keyword signal weights.
    """
    if not isinstance(weights, dict):
        raise ValueError(f"Signal weights must be a dictionary, got {type(weights).__name__}")

    validated: Dict[str, int] = {}
    for kw, wt in weights.items():
        if not isinstance(kw, str) or not kw.strip():
            raise ValueError(f"Signal keyword must be a non-empty string, got: {kw}")
        val = validate_numeric_weight(f"signal.{kw}", wt)
        validated[kw.strip().lower()] = int(val)

    return validated


def validate_aggregation_strategy(strategy: Any) -> str:
    """
    Validate that the aggregation strategy is supported.
    """
    if not isinstance(strategy, str):
        raise ValueError(
            f"Aggregation strategy must be a string, got {type(strategy).__name__}: {strategy}"
        )
    strat_lower = strategy.strip().lower()
    if strat_lower not in ALLOWED_AGGREGATION_STRATEGIES:
        raise ValueError(
            f"Invalid aggregation strategy '{strategy}'. "
            f"Allowed strategies: {sorted(ALLOWED_AGGREGATION_STRATEGIES)}"
        )
    return strat_lower


def validate_aggregation_top_k(top_k: Any) -> int:
    """
    Validate that aggregation top_k is a positive integer.
    """
    if not isinstance(top_k, int) or isinstance(top_k, bool):
        try:
            top_k = int(top_k)
        except (ValueError, TypeError):
            raise ValueError(f"Aggregation top_k must be an integer, got {top_k}")
    if top_k <= 0:
        raise ValueError(f"Aggregation top_k must be greater than zero, got {top_k}")
    return top_k


def validate_trend_window_days(days: Any) -> int:
    """
    Validate that trend rolling window days is a positive integer.
    """
    if not isinstance(days, int) or isinstance(days, bool):
        try:
            days = int(days)
        except (ValueError, TypeError):
            raise ValueError(f"Trend window days must be an integer, got {days}")
    if days <= 0:
        raise ValueError(f"Trend window days must be greater than zero, got {days}")
    return days


def validate_trend_direction_threshold(threshold: Any) -> float:
    """
    Validate that trend direction delta threshold is a non-negative float.
    """
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
        raise ValueError(
            f"Trend direction threshold must be numeric, got {type(threshold).__name__}: {threshold}"
        )
    if threshold < 0:
        raise ValueError(f"Trend direction threshold cannot be negative, got {threshold}")
    return float(threshold)


def validate_factor_weight(name: str, value: Any, max_val: float = 1.0) -> float:
    """
    Validate that a weight factor is numeric and in [0.0, max_val].
    """
    val = validate_numeric_weight(name, value, allow_zero=True)
    if val > max_val:
        raise ValueError(f"Weight '{name}' cannot exceed {max_val}, got {val}")
    return val


# ------------------------------------------------------------------
# Configuration Settings Class
# ------------------------------------------------------------------

class Settings:
    """
    Supplier risk scoring configuration settings.
    Can be initialized from environment variables or overridden dynamically.
    """

    def __init__(
        self,
        negative_sentiment_penalty: float | None = None,
        neutral_sentiment_penalty: float | None = None,
        positive_sentiment_penalty: float | None = None,
        signal_weights: Dict[str, int] | None = None,
        max_risk_score: float | None = None,
        confidence_divisor: float | None = None,
        aggregation_strategy: str | None = None,
        aggregation_top_k: int | None = None,
        recency_half_life_days: float | None = None,
        trend_window_days: int | None = None,
        trend_direction_threshold: float | None = None,
        tier_low_ceiling: float | None = None,
        tier_medium_ceiling: float | None = None,
        tier_high_ceiling: float | None = None,
        volume_weight: float | None = None,
        mitigation_weight: float | None = None,
    ) -> None:
        # 1. Negative sentiment penalty
        if negative_sentiment_penalty is not None:
            self.negative_sentiment_penalty = validate_numeric_weight(
                "negative_sentiment_penalty", negative_sentiment_penalty
            )
        else:
            raw = os.getenv("NEGATIVE_SENTIMENT_PENALTY")
            self.negative_sentiment_penalty = (
                validate_numeric_weight("NEGATIVE_SENTIMENT_PENALTY", float(raw))
                if raw is not None
                else DEFAULT_NEGATIVE_SENTIMENT_PENALTY
            )

        # 2. Neutral sentiment penalty
        if neutral_sentiment_penalty is not None:
            self.neutral_sentiment_penalty = validate_numeric_weight(
                "neutral_sentiment_penalty", neutral_sentiment_penalty
            )
        else:
            raw = os.getenv("NEUTRAL_SENTIMENT_PENALTY")
            self.neutral_sentiment_penalty = (
                validate_numeric_weight("NEUTRAL_SENTIMENT_PENALTY", float(raw))
                if raw is not None
                else DEFAULT_NEUTRAL_SENTIMENT_PENALTY
            )

        # 3. Positive sentiment penalty
        if positive_sentiment_penalty is not None:
            self.positive_sentiment_penalty = validate_numeric_weight(
                "positive_sentiment_penalty", positive_sentiment_penalty
            )
        else:
            raw = os.getenv("POSITIVE_SENTIMENT_PENALTY")
            self.positive_sentiment_penalty = (
                validate_numeric_weight("POSITIVE_SENTIMENT_PENALTY", float(raw))
                if raw is not None
                else DEFAULT_POSITIVE_SENTIMENT_PENALTY
            )

        # 4. Max risk score
        if max_risk_score is not None:
            self.max_risk_score = validate_numeric_weight(
                "max_risk_score", max_risk_score, allow_zero=False
            )
        else:
            raw = os.getenv("MAX_RISK_SCORE")
            self.max_risk_score = (
                validate_numeric_weight("MAX_RISK_SCORE", float(raw), allow_zero=False)
                if raw is not None
                else DEFAULT_MAX_RISK_SCORE
            )

        # 5. Confidence saturation divisor
        if confidence_divisor is not None:
            self.confidence_divisor = validate_numeric_weight(
                "confidence_divisor", confidence_divisor, allow_zero=False
            )
        else:
            raw = os.getenv("CONFIDENCE_DIVISOR")
            self.confidence_divisor = (
                validate_numeric_weight("CONFIDENCE_DIVISOR", float(raw), allow_zero=False)
                if raw is not None
                else DEFAULT_CONFIDENCE_DIVISOR
            )

        # 6. Signal weights
        if signal_weights is not None:
            self.signal_weights = validate_signal_weights(signal_weights)
        else:
            raw_json = os.getenv("SIGNAL_WEIGHTS_JSON")
            if raw_json:
                try:
                    parsed = json.loads(raw_json)
                    self.signal_weights = validate_signal_weights(parsed)
                except Exception as exc:
                    raise ValueError(f"Invalid SIGNAL_WEIGHTS_JSON environment variable: {exc}") from exc
            else:
                self.signal_weights = dict(DEFAULT_SIGNAL_WEIGHTS)

        # 7. Risk score aggregation strategy
        if aggregation_strategy is not None:
            self.aggregation_strategy = validate_aggregation_strategy(aggregation_strategy)
        else:
            raw_strat = os.getenv("AGGREGATION_STRATEGY")
            self.aggregation_strategy = (
                validate_aggregation_strategy(raw_strat)
                if raw_strat is not None
                else DEFAULT_AGGREGATION_STRATEGY
            )

        # 8. Aggregation top-k
        if aggregation_top_k is not None:
            self.aggregation_top_k = validate_aggregation_top_k(aggregation_top_k)
        else:
            raw_top_k = os.getenv("AGGREGATION_TOP_K")
            self.aggregation_top_k = (
                validate_aggregation_top_k(int(raw_top_k))
                if raw_top_k is not None
                else DEFAULT_AGGREGATION_TOP_K
            )

        # 9. Recency half-life days
        if recency_half_life_days is not None:
            self.recency_half_life_days = validate_numeric_weight(
                "recency_half_life_days", recency_half_life_days, allow_zero=False
            )
        else:
            raw_recency = os.getenv("RECENCY_HALF_LIFE_DAYS")
            self.recency_half_life_days = (
                validate_numeric_weight("RECENCY_HALF_LIFE_DAYS", float(raw_recency), allow_zero=False)
                if raw_recency is not None
                else DEFAULT_RECENCY_HALF_LIFE_DAYS
            )

        # 10. Fixed risk tier thresholds (configured a priori before evaluation)
        if tier_low_ceiling is not None:
            self.tier_low_ceiling = validate_numeric_weight("tier_low_ceiling", tier_low_ceiling, allow_zero=False)
        else:
            raw_low = os.getenv("TIER_LOW_CEILING")
            self.tier_low_ceiling = (
                validate_numeric_weight("TIER_LOW_CEILING", float(raw_low), allow_zero=False)
                if raw_low is not None
                else DEFAULT_TIER_LOW_CEILING
            )

        if tier_medium_ceiling is not None:
            self.tier_medium_ceiling = validate_numeric_weight("tier_medium_ceiling", tier_medium_ceiling, allow_zero=False)
        else:
            raw_med = os.getenv("TIER_MEDIUM_CEILING")
            self.tier_medium_ceiling = (
                validate_numeric_weight("TIER_MEDIUM_CEILING", float(raw_med), allow_zero=False)
                if raw_med is not None
                else DEFAULT_TIER_MEDIUM_CEILING
            )

        if tier_high_ceiling is not None:
            self.tier_high_ceiling = validate_numeric_weight("tier_high_ceiling", tier_high_ceiling, allow_zero=False)
        else:
            raw_high = os.getenv("TIER_HIGH_CEILING")
            self.tier_high_ceiling = (
                validate_numeric_weight("TIER_HIGH_CEILING", float(raw_high), allow_zero=False)
                if raw_high is not None
                else DEFAULT_TIER_HIGH_CEILING
            )

        if not (self.tier_low_ceiling < self.tier_medium_ceiling < self.tier_high_ceiling):
            raise ValueError(
                f"Tier ceilings must satisfy low < medium < high, got: "
                f"low={self.tier_low_ceiling}, medium={self.tier_medium_ceiling}, high={self.tier_high_ceiling}"
            )

        # 11. Trend rolling window days
        if trend_window_days is not None:
            self.trend_window_days = validate_trend_window_days(trend_window_days)
        else:
            raw_win = os.getenv("TREND_WINDOW_DAYS", os.getenv("ROLLING_WINDOW_DAYS"))
            self.trend_window_days = (
                validate_trend_window_days(int(raw_win))
                if raw_win is not None
                else DEFAULT_TREND_WINDOW_DAYS
            )

        # 12. Trend direction sensitivity threshold
        if trend_direction_threshold is not None:
            self.trend_direction_threshold = validate_trend_direction_threshold(trend_direction_threshold)
        else:
            raw_thresh = os.getenv("TREND_DIRECTION_THRESHOLD")
            self.trend_direction_threshold = (
                validate_trend_direction_threshold(float(raw_thresh))
                if raw_thresh is not None
                else DEFAULT_TREND_DIRECTION_THRESHOLD
            )

        # 13. Volume amplification weight (top_k_mean)
        if volume_weight is not None:
            self.volume_weight = validate_factor_weight("volume_weight", volume_weight)
        else:
            raw_vol = os.getenv("VOLUME_WEIGHT")
            self.volume_weight = (
                validate_factor_weight("VOLUME_WEIGHT", float(raw_vol))
                if raw_vol is not None
                else DEFAULT_VOLUME_WEIGHT
            )

        # 14. Mitigation discount weight (top_k_mean)
        if mitigation_weight is not None:
            self.mitigation_weight = validate_factor_weight("mitigation_weight", mitigation_weight)
        else:
            raw_mit = os.getenv("MITIGATION_WEIGHT")
            self.mitigation_weight = (
                validate_factor_weight("MITIGATION_WEIGHT", float(raw_mit))
                if raw_mit is not None
                else DEFAULT_MITIGATION_WEIGHT
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings instance to dictionary for API serialization."""
        return {
            "model_name": MODEL_NAME,
            "negative_sentiment_penalty": self.negative_sentiment_penalty,
            "neutral_sentiment_penalty": self.neutral_sentiment_penalty,
            "positive_sentiment_penalty": self.positive_sentiment_penalty,
            "max_risk_score": self.max_risk_score,
            "confidence_divisor": self.confidence_divisor,
            "aggregation_strategy": self.aggregation_strategy,
            "aggregation_top_k": self.aggregation_top_k,
            "recency_half_life_days": self.recency_half_life_days,
            "tier_low_ceiling": self.tier_low_ceiling,
            "tier_medium_ceiling": self.tier_medium_ceiling,
            "tier_high_ceiling": self.tier_high_ceiling,
            "trend_window_days": self.trend_window_days,
            "trend_direction_threshold": self.trend_direction_threshold,
            "volume_weight": self.volume_weight,
            "mitigation_weight": self.mitigation_weight,
            "signal_weights": dict(self.signal_weights),
        }


@lru_cache
def get_settings() -> Settings:
    """Get the active configuration settings (cached)."""
    return Settings()


# Global active settings instance (retained for backward compatibility)
settings = get_settings()
