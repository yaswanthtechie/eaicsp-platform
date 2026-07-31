"""
Prediction module that orchestrates the NLP pipeline for supplier risk scoring.
"""
from typing import Any, Dict, List
from preprocess import clean_text
from sentiment import analyze_sentiment
from signals import detect_signals

def predict(supplier_name: str, headlines: List[str]) -> Dict[str, Any]:
    """
    Predict the overall risk score and summarize sentiment and signals for a supplier.
    
    Args:
        supplier_name (str): Name of the supplier.
        headlines (List[str]): List of news headlines for the supplier.
        
    Returns:
        Dict[str, Any]: Aggregated risk analysis results, capping risk_score at 100.
    """
    sentiment_breakdown = {"positive": 0, "neutral": 0, "negative": 0}
    all_signals: List[Dict[str, Any]] = []
    
    total_headline_score = 0.0
    processed_headlines = []
    
    for headline in headlines:
        # Sentiment Analysis (done on raw text, as FinBERT handles its own tokenization)
        sentiment_res = analyze_sentiment(headline)
        label = sentiment_res["label"]
        confidence = sentiment_res["confidence"]
        
        sentiment_breakdown[label] += 1
        
        # Signal Detection (done on preprocessed text)
        cleaned_text = clean_text(headline)
        detected_signals = detect_signals(cleaned_text)
        
        signal_score = sum(sig["weight"] for sig in detected_signals)
        
        # Add to all signals
        all_signals.extend(detected_signals)
        
        # Sentiment Penalty
        sentiment_penalty = 0.0
        if label == "negative":
            sentiment_penalty = 30.0 * confidence
        elif label == "neutral":
            sentiment_penalty = 10.0 * confidence
            
        headline_score = sentiment_penalty + signal_score
        total_headline_score += headline_score
        
        processed_headlines.append({
            "headline": headline,
            "sentiment": label,
            "score": round(headline_score, 2),
            "signals": detected_signals
        })
        
    # Calculate overall risk score
    num_headlines = len(headlines)
    avg_score = total_headline_score / num_headlines if num_headlines > 0 else 0
    final_risk_score = min(100.0, avg_score)
    
    # Identify top 3 worst headlines (highest score)
    sorted_headlines = sorted(processed_headlines, key=lambda x: x["score"], reverse=True) # type: ignore
    top_worst_3 = sorted_headlines[:3]
    
    # Deduplicate signals for the final output report
    # We use a dictionary keyed by the signal keyword to ensure uniqueness
    unique_signals_dict = {}
    for sig in all_signals:
        unique_signals_dict[sig["keyword"]] = sig
    
    return {
        "supplier": supplier_name,
        "risk_score": round(final_risk_score, 2),
        "sentiment_breakdown": sentiment_breakdown,
        "signals": list(unique_signals_dict.values()),
        "top_worst_3": top_worst_3
    }
