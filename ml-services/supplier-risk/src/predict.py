"""
Prediction module that orchestrates the NLP pipeline
for supplier risk scoring.
"""

import math
from typing import Any, Dict, List

from src.preprocess import clean_text
from src.sentiment import analyze_sentiment
from src.signals import detect_signals


def _calculate_confidence(num_headlines: int) -> float:
    """
    Calculate a volume-based evidence strength (confidence) score.

    Uses an exponential saturation curve that increases smoothly
    with headline count and asymptotically approaches 1.0.

    Formula: confidence = 1 - exp(-n / 8)

    Key properties:
    - n = 0  → 0.00 (no evidence)
    - n = 1  → 0.12 (very low)
    - n = 2  → 0.22 (low)
    - n = 5  → 0.46 (moderate)
    - n = 10 → 0.71 (high)
    - n = 20 → 0.92 (very high)
    - n → ∞  → ~1.0 (approaches full confidence)

    The divisor 8 is chosen so that the typical dataset size of
    12 headlines/company yields ~0.78 confidence (substantial but
    not absolute), matching the Round 4 calibration dataset.
    """
    if num_headlines <= 0:
        return 0.0
    return round(
        1.0 - math.exp(-num_headlines / 8.0),
        4,
    )


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


def _sentiment_penalty(label: str, confidence: float) -> float:
    """
    Calculate sentiment penalty based on sentiment label.
    """

    if label == "negative":
        return 40.0 * confidence

    if label == "neutral":
        return 0.0

    return 0.0


def predict(
    supplier_name: str,
    headlines: List[str],
) -> Dict[str, Any]:
    """
    Predict supplier risk score using sentiment analysis
    and keyword-based signal detection.
    """

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
        confidence = float(
            sentiment_result.get("confidence", 1.0)
        )

        if label not in sentiment_breakdown:
            label = "neutral"

        sentiment_breakdown[label] += 1

        # -------------------------
        # Signal Detection
        # -------------------------

        cleaned_text = clean_text(headline)

        detected_signals = detect_signals(cleaned_text)

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

    peak_score = min(
        100.0,
        max(item["score"] for item in processed_headlines),
    )

    average_score = (
        total_headline_score / len(processed_headlines)
    )

    blended_score = (
        0.8 * average_score + 0.2 * peak_score
    )

    final_risk_score = min(
        100.0,
        blended_score,
    )

    # ----------------------------------------
    # Top 3 Highest Risk Headlines
    # ----------------------------------------

    top_worst_3 = sorted(
        processed_headlines,
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
        len(processed_headlines),
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