"""
Prediction module that orchestrates the NLP pipeline
for supplier risk scoring.
"""

from typing import Any, Dict, List
from preprocess import clean_text
from sentiment import analyze_sentiment
from signals import detect_signals


def _empty_response(supplier_name: str) -> Dict[str, Any]:
    """
    Return an empty response when no headlines are available.
    """
    return {
        "supplier": supplier_name,
        "risk_score": 0.0,
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
        return 30.0 * confidence

    if label == "neutral":
        return 10.0 * confidence

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

    sentiment_breakdown = {
        "positive": 0,
        "neutral": 0,
        "negative": 0,
    }

    processed_headlines: List[Dict[str, Any]] = []
    all_signals: List[Dict[str, Any]] = []

    total_headline_score = 0.0

    for headline in headlines:

        # Skip empty headlines
        if not headline or not headline.strip():
            continue

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

    average_score = (
        total_headline_score / len(processed_headlines)
    )

    final_risk_score = min(
        100.0,
        average_score,
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
    # Final Response
    # ----------------------------------------

    return {
        "supplier": supplier_name,
        "risk_score": round(final_risk_score, 2),
        "sentiment_breakdown": sentiment_breakdown,
        "signals": list(unique_signals.values()),
        "top_worst_3": top_worst_3,
    }