"""
Prediction module that orchestrates the NLP pipeline
for supplier risk scoring.
"""

import math
from typing import Any, Dict, List, Optional

from src.config import (
    DEFAULT_MITIGATION_WEIGHT,
    DEFAULT_VOLUME_WEIGHT,
    Settings,
    get_settings,
)
from src.preprocess import clean_text
from src.sentiment import analyze_sentiment
from src.signals import detect_signals


def _calculate_confidence(
    evidence: Any,
    divisor: float = 8.0,
) -> float:
    """
    Calculate confidence based on signal agreement, proportion of meaningful signals,
    score dispersion, and evidence strength.

    If an integer is passed (backward compatibility), falls back to volume saturation.
    If a list of processed headlines is passed, evaluates:
    - Proportion of meaningful risk-bearing headlines (signal vs noise)
    - Agreement / consistency of headline risk scores (low dispersion -> higher confidence)
    - Signal strength (magnitude of peak risk detected)
    - Saturated evidence volume based on meaningful signal count so neutral padding
      cannot artificially inflate confidence.
    """
    safe_divisor = divisor if divisor > 0 else 8.0

    if isinstance(evidence, (int, float)):
        if evidence <= 0:
            return 0.0
        return round(1.0 - math.exp(-float(evidence) / safe_divisor), 4)

    if not isinstance(evidence, list) or not evidence:
        return 0.0

    processed_headlines = evidence
    num_headlines = len(processed_headlines)
    if num_headlines == 0:
        return 0.0

    # Identify risk-bearing / meaningful headlines
    risk_headlines = [
        item for item in processed_headlines
        if item.get("score", 0.0) > 0 or len(item.get("signals", [])) > 0 or item.get("sentiment") == "negative"
    ]
    num_risk = len(risk_headlines)

    if num_risk > 0:
        signal_proportion = num_risk / num_headlines
        volume_factor = 1.0 - math.exp(-num_risk / safe_divisor)

        scores = [item.get("score", 0.0) for item in risk_headlines]
        if len(scores) <= 1:
            agreement = 1.0
        else:
            mean_score = sum(scores) / len(scores)
            variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
            std_dev = math.sqrt(variance)
            dispersion = min(1.0, std_dev / 50.0)
            agreement = max(0.0, 1.0 - dispersion)

        peak_score = max(scores)
        strength = min(1.0, peak_score / 100.0)

        raw_conf = volume_factor * (
            0.35 + 0.25 * signal_proportion + 0.25 * agreement + 0.15 * strength
        )
    else:
        # All headlines are neutral/clean: confidence reflects certainty in the clean assessment
        volume_factor = 1.0 - math.exp(-num_headlines / safe_divisor)
        raw_conf = volume_factor * 0.5

    return round(min(1.0, max(0.0, raw_conf)), 4)




def _calculate_top_k_mean_aggregated_score(
    processed_headlines: List[Dict[str, Any]],
    top_k: int,
    volume_weight: float = DEFAULT_VOLUME_WEIGHT,
    mitigation_weight: float = DEFAULT_MITIGATION_WEIGHT,
) -> float:
    """
    Calculate risk score under the principled top_k_mean strategy.

    Combines:
    1. Risk Intensity / Severity: Average of top-k risk-bearing headline scores.
    2. Risk Coverage Volume: Monotonically scales risk when repeated adverse
       events are detected (saturation curve with diminishing marginal increases).
    3. Positive / Mitigating Coverage: Mitigating headlines genuinely reduce the
       risk score proportionally to positive evidence in the headline sample.
    """
    risk_scores = [item["score"] for item in processed_headlines if item.get("score", 0.0) > 0]
    if not risk_scores:
        return 0.0

    sorted_risk_scores = sorted(risk_scores, reverse=True)

    # 1. Severity: Average of top-k risk-bearing headline scores
    top_k_scores = sorted_risk_scores[:top_k]
    severity_base = sum(top_k_scores) / len(top_k_scores)

    # 2. Volume Factor: Repeated negative coverage amplifies risk with diminishing returns
    num_risk = len(sorted_risk_scores)
    volume_factor = 1.0 + volume_weight * (1.0 - 1.0 / num_risk) if num_risk > 1 else 1.0

    # 3. Mitigating Positive Coverage: Clean positive headlines genuinely reduce risk
    positive_headlines = [
        item for item in processed_headlines
        if item.get("sentiment") == "positive" and item.get("score", 0.0) == 0
    ]
    num_pos = len(positive_headlines)
    num_total = len(processed_headlines)
    positive_ratio = (num_pos / num_total) if num_total > 0 else 0.0
    mitigation_factor = 1.0 - mitigation_weight * positive_ratio

    return severity_base * volume_factor * mitigation_factor


def _aggregate_risk_score(
    processed_headlines: List[Dict[str, Any]],
    config: Settings,
) -> float:
    """
    Aggregate headline risk scores into a final supplier risk score
    based on the configured aggregation strategy.

    Supported strategies:
    - "top_k_mean" (default): Principled anti-dilution strategy that combines:
      1. Peak severity: Top-k mean of risk-bearing headline scores.
      2. Risk coverage volume: Saturation curve scaling with repeated risk events.
      3. Positive mitigation: Mitigating factor scaling with positive coverage proportion.
    - "max": Uses the worst-case (maximum) headline risk score.
    - "blend": Backward-compatible 80% average / 20% peak blend.
    - "mean": Backward-compatible unweighted mean of all headlines.
    """
    if not processed_headlines:
        return 0.0

    strategy = config.aggregation_strategy
    top_k = config.aggregation_top_k
    scores = [item["score"] for item in processed_headlines]

    if strategy == "max":
        raw_score = max(scores)

    elif strategy == "blend":
        peak_score = max(scores)
        average_score = sum(scores) / len(scores)
        raw_score = 0.8 * average_score + 0.2 * peak_score

    elif strategy == "mean":
        raw_score = sum(scores) / len(scores)

    elif strategy == "top_k_mean":
        raw_score = _calculate_top_k_mean_aggregated_score(
            processed_headlines=processed_headlines,
            top_k=top_k,
            volume_weight=config.volume_weight,
            mitigation_weight=config.mitigation_weight,
        )
    else:
        raw_score = _calculate_top_k_mean_aggregated_score(
            processed_headlines=processed_headlines,
            top_k=top_k,
            volume_weight=config.volume_weight,
            mitigation_weight=config.mitigation_weight,
        )

    return min(config.max_risk_score, max(0.0, raw_score))


def _empty_response(supplier_name: str) -> Dict[str, Any]:
    """
    Return an empty response when no headlines are available.
    """
    return {
        "supplier": supplier_name,
        "risk_score": 0.0,
        "confidence": 0.0,
        "sentiment_breakdown": {
            "positive": 0,
            "neutral": 0,
            "negative": 0,
        },
        "signals": [],
        "top_worst_3": [],
    }


def _sentiment_penalty(
    label: str,
    confidence: float,
    config: Settings,
) -> float:
    """
    Calculate sentiment penalty based on configurable settings.
    """
    if label == "negative":
        return config.negative_sentiment_penalty * confidence
    if label == "neutral":
        return config.neutral_sentiment_penalty * confidence
    if label == "positive":
        return config.positive_sentiment_penalty * confidence
    return 0.0


def predict(
    supplier_name: str,
    headlines: List[str],
    config: Optional[Settings] = None,
) -> Dict[str, Any]:
    """
    Predict supplier risk score using sentiment analysis
    and keyword-based signal detection driven by configuration settings.
    """
    cfg = config if config is not None else get_settings()

    if not headlines:
        return _empty_response(supplier_name)

    # ----------------------------------------
    # Deduplicate Headlines (case & whitespace insensitive)
    # ----------------------------------------
    seen_headlines = set()
    unique_headlines: List[str] = []

    for headline in headlines:
        if not headline or not headline.strip():
            continue
        normalized = headline.strip().lower()
        if normalized not in seen_headlines:
            seen_headlines.add(normalized)
            unique_headlines.append(headline.strip())

    if not unique_headlines:
        return _empty_response(supplier_name)

    sentiment_breakdown = {
        "positive": 0,
        "neutral": 0,
        "negative": 0,
    }

    processed_headlines: List[Dict[str, Any]] = []
    all_signals: List[Dict[str, Any]] = []

    total_headline_score = 0.0

    for headline in unique_headlines:
        # -------------------------
        # Sentiment Analysis
        # -------------------------
        sentiment_result = analyze_sentiment(headline)

        label = sentiment_result.get("label", "neutral")
        confidence = float(sentiment_result.get("confidence", 1.0))

        if label not in sentiment_breakdown:
            label = "neutral"

        sentiment_breakdown[label] += 1

        # -------------------------
        # Signal Detection
        # -------------------------
        cleaned_text = clean_text(headline)
        detected_signals = detect_signals(
            cleaned_text,
            weights=cfg.signal_weights,
        )

        signal_score = sum(
            signal["weight"]
            for signal in detected_signals
        )

        all_signals.extend(detected_signals)

        # -------------------------
        # Headline Score
        # -------------------------
        headline_score = (
            _sentiment_penalty(
                label,
                confidence,
                cfg,
            )
            + signal_score
        )

        total_headline_score += headline_score

        processed_headlines.append(
            {
                "headline": headline,
                "sentiment": label,
                "score": round(headline_score, 2),
                "signals": detected_signals,
            }
        )

    # ----------------------------------------
    # No Valid Headlines
    # ----------------------------------------
    if not processed_headlines:
        return _empty_response(supplier_name)

    # ----------------------------------------
    # Final Risk Score
    # ----------------------------------------
    final_risk_score = _aggregate_risk_score(
        processed_headlines,
        config=cfg,
    )

    # ----------------------------------------
    # Top 3 Highest Risk Headlines (Score > 0 only)
    # ----------------------------------------
    risk_bearing_headlines = [
        item for item in processed_headlines if item["score"] > 0
    ]
    top_worst_3 = sorted(
        risk_bearing_headlines,
        key=lambda item: item["score"],
        reverse=True,
    )[:3]


    # ----------------------------------------
    # Remove Duplicate Signals
    # ----------------------------------------
    unique_signals: Dict[str, Dict[str, Any]] = {}
    for signal in all_signals:
        keyword = signal.get("keyword")
        if keyword:
            unique_signals[keyword] = signal

    # ----------------------------------------
    # Confidence / Evidence Strength
    # ----------------------------------------
    confidence = _calculate_confidence(
        processed_headlines,
        divisor=cfg.confidence_divisor,
    )

    # ----------------------------------------
    # Final Response
    # ----------------------------------------
    return {
        "supplier": supplier_name,
        "risk_score": round(final_risk_score, 2),
        "confidence": confidence,
        "sentiment_breakdown": sentiment_breakdown,
        "signals": list(unique_signals.values()),
        "top_worst_3": top_worst_3,
    }