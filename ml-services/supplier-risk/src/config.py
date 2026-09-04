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


@lru_cache
def get_settings() -> Settings:
    """Get the active configuration settings (cached)."""
    return Settings()


# Global active settings instance (retained for backward compatibility)
settings = get_settings()
