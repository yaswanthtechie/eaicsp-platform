"""
Sentiment analysis module using HuggingFace's FinBERT.
"""
from typing import Any, Dict

# Global variable to hold the initialized model pipeline
_nlp_pipeline = None

def init_model() -> None:
    """
    Initialize the FinBERT model pipeline. Should be called during application startup.
    """
    global _nlp_pipeline
    if _nlp_pipeline is None:
        try:
            from transformers import pipeline
        except ModuleNotFoundError as e:
            raise ModuleNotFoundError(
                "Missing dependency 'transformers'. Install it with: python -m pip install -r requirements.txt"
            ) from e
        _nlp_pipeline = pipeline("text-classification", model="ProsusAI/finbert")

def analyze_sentiment(text: str) -> Dict[str, Any]:
    """
    Analyze the sentiment of the provided text using FinBERT.
    
    Args:
        text (str): The input text to analyze.
        
    Returns:
        Dict[str, Any]: A dictionary containing the 'label' and 'confidence'.
            Example: {"label": "negative", "confidence": 0.95}
    """
    global _nlp_pipeline
    
    if _nlp_pipeline is None:
        # Fallback initialization if not explicitly initialized
        init_model()
        
    # Handle empty string
    if not text.strip():
        return {"label": "neutral", "confidence": 1.0}
        
    result = _nlp_pipeline(text)[0] # type: ignore
    return {
        "label": result["label"].lower(),
        "confidence": result["score"]
    }
