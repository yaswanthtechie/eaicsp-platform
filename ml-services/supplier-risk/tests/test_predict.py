"""
Unit tests for the Supplier Risk NLP pipeline.
"""
# pyrefly: ignore [missing-import]
import pytest
# pyrefly: ignore [missing-import]
from preprocess import clean_text
# pyrefly: ignore [missing-import]
from signals import detect_signals, SIGNAL_WEIGHTS
# pyrefly: ignore [missing-import]
from predict import predict
# pyrefly: ignore [missing-import]
from data import load_headlines

def test_preprocess_cleans_text():
    """Test that preprocess removes punctuation, lowercases, and strips extra spaces."""
    raw_text = "  TechCorp files for BANKRUPTCY, after massive fraud... scandal!  "
    expected = "techcorp files for bankruptcy after massive fraud scandal"
    assert clean_text(raw_text) == expected

def test_keyword_detection():
    """Test that keyword detection finds keywords and assigns correct weights."""
    text = clean_text("TechCorp files for bankruptcy after massive fraud scandal")
    signals = detect_signals(text)
    
    # Extract keywords from the detected signals
    keywords_found = [sig["keyword"] for sig in signals]
    
    assert "bankruptcy" in keywords_found
    assert "fraud" in keywords_found
    assert "strike" not in keywords_found
    
    # Check weights
    for sig in signals:
        assert sig["weight"] == SIGNAL_WEIGHTS[sig["keyword"]]

def test_bankruptcy_higher_risk_than_strike():
    """Test that the risk score for bankruptcy is higher than for a strike."""
    supplier = "TestSupplier"
    
    # Only sending neutral/positive sentiment to isolate signal weight
    # We mock out sentiment analysis effect by having similar neutral sentences
    bankruptcy_headlines = ["The company faces bankruptcy."]
    strike_headlines = ["The company faces a strike."]
    
    res_bankruptcy = predict(supplier, bankruptcy_headlines)
    res_strike = predict(supplier, strike_headlines)
    
    assert res_bankruptcy["risk_score"] > res_strike["risk_score"]

def test_predict_schema():
    """Test that the predict function returns the exact required JSON schema."""
    supplier = "TechCorp"
    headlines = ["TechCorp files for bankruptcy after massive fraud scandal."]
    
    result = predict(supplier, headlines)
    
    assert "supplier" in result
    assert result["supplier"] == "TechCorp"
    
    assert "risk_score" in result
    assert isinstance(result["risk_score"], (int, float))
    assert result["risk_score"] <= 100
    
    assert "sentiment_breakdown" in result
    assert "positive" in result["sentiment_breakdown"]
    assert "neutral" in result["sentiment_breakdown"]
    assert "negative" in result["sentiment_breakdown"]
    
    assert "signals" in result
    assert isinstance(result["signals"], list)
    if result["signals"]:
        assert "keyword" in result["signals"][0]
        assert "weight" in result["signals"][0]
        
    assert "top_worst_3" in result
    assert isinstance(result["top_worst_3"], list)
    if result["top_worst_3"]:
        assert "headline" in result["top_worst_3"][0]
        assert "sentiment" in result["top_worst_3"][0]
        assert "score" in result["top_worst_3"][0]
        assert "signals" in result["top_worst_3"][0]

def test_fraud_increases_score():
    """Test that the presence of fraud increases the risk score."""
    supplier = "FraudSupplier"
    base_headlines = ["The company reported its earnings."]
    fraud_headlines = ["The company reported its earnings and is under investigation for fraud."]
    
    res_base = predict(supplier, base_headlines)
    res_fraud = predict(supplier, fraud_headlines)
    
    assert res_fraud["risk_score"] > res_base["risk_score"]

def test_multiple_signals_combine():
    """Test that multiple signals add up correctly in the score."""
    supplier = "ComboSupplier"
    # We use neutral/positive context to isolate signal weights
    single_headline = ["The company faces a strike."]
    combo_headline = ["The company faces a strike and a lawsuit."]
    
    res_single = predict(supplier, single_headline)
    res_combo = predict(supplier, combo_headline)
    
    assert res_combo["risk_score"] > res_single["risk_score"]

def test_score_never_exceeds_100():
    """Test that the final score is capped at 100."""
    supplier = "DoomedSupplier"
    headlines = [
        "The company is facing bankruptcy, default, fraud, sanction, and investigation while workers strike."
    ] * 5  # High negative sentiment + high signal weight
    
    result = predict(supplier, headlines)
    assert result["risk_score"] <= 100.0

def test_evaluation_dataset():
    """Verify that the evaluation dataset has the required properties."""
    import json
    import os
    
    dataset_path = os.path.join(os.path.dirname(__file__), "..", "src", "supplier_headlines.json")
    
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
        
    assert isinstance(dataset, list)
    assert len(dataset) == 50, f"Expected 50 headlines, found {len(dataset)}"
    
    from collections import defaultdict
    grouped = defaultdict(list)
    for item in dataset:
        assert "supplier" in item
        assert "headline" in item
        grouped[item["supplier"]].append(item["headline"])
        
    assert len(grouped) == 5, f"Expected 5 suppliers, found {len(grouped)}"
    
    for supplier, headlines in grouped.items():
        assert len(headlines) == 10, f"Expected 10 headlines for {supplier}, found {len(headlines)}"
