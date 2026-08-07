"""
Sentiment analysis module using HuggingFace's FinBERT.
"""

from typing import Any, Dict

try:
    # pyrefly: ignore [missing-import]
    from transformers import pipeline
except ModuleNotFoundError as e:
    raise ModuleNotFoundError(
        "Missing dependency 'transformers'. "
        "Install it using:\n"
        "python -m pip install -r requirements.txt"
    ) from e


# Global variable to hold the initialized model pipeline
_nlp_pipeline = None


def init_model() -> None:
    """
    Initialize the FinBERT model pipeline.

    This should be called during FastAPI startup.
    The model is loaded only once.
    """
    global _nlp_pipeline

    if _nlp_pipeline is None:
        _nlp_pipeline = pipeline(
            "text-classification",
            model="ProsusAI/finbert"
        )


def analyze_sentiment(text: str) -> Dict[str, Any]:
    """
    Analyze the sentiment of the provided text using FinBERT.

    Args:
        text (str): Input text.

    Returns:
        Dict[str, Any]:
            Example:
            {
                "label": "negative",
                "confidence": 0.95
            }
    """

    global _nlp_pipeline

    # Lazy initialization
    if _nlp_pipeline is None:
        init_model()

    # Handle empty input
    if not text or not text.strip():
        return {
            "label": "neutral",
            "confidence": 1.0
        }

    # Run inference
    result = _nlp_pipeline(
        text,
        truncation=True,
        max_length=512
    )[0]

    return {
        "label": result["label"].lower(),
        "confidence": float(result["score"])
    }