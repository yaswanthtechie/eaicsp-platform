"""
Integration tests for the Supplier Risk NLP pipeline.
"""

import pytest
from src.predict import predict
from src.data import load_headlines

@pytest.mark.slow
def test_real_sentiment_integration():
    """
    Test using the real sentiment model and real dataset.
    Asserts that a known risky supplier (Tesla) scores higher 
    than a more stable supplier (TSMC).
    """
    # Load real dataset
    data = load_headlines()
    
    # We must ensure we have headlines for Tesla and TSMC in the dataset
    assert "Tesla" in data, "Tesla not found in dataset"
    assert "TSMC" in data, "TSMC not found in dataset"
    
    tesla_headlines = data["Tesla"]
    tsmc_headlines = data["TSMC"]
    
    # Run prediction using the REAL sentiment model
    tesla_result = predict("Tesla", tesla_headlines)
    tsmc_result = predict("TSMC", tsmc_headlines)
    
    # Check that Tesla risk score > TSMC risk score
    tesla_score = tesla_result["risk_score"]
    tsmc_score = tsmc_result["risk_score"]
    
    assert tesla_score > tsmc_score, f"Expected Tesla risk ({tesla_score}) > TSMC risk ({tsmc_score})"
