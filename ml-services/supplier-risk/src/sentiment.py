"""
Sentiment analysis module using HuggingFace FinBERT.
"""

from typing import Any, Dict, Final, Optional

try:
    # pyrefly: ignore [missing-import]
    from transformers import pipeline
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "Missing dependency 'transformers'.\n"
        "Install project dependencies using:\n"
        "python -m pip install -r requirements.txt"
    ) from exc


from src.config import MODEL_NAME

# Global pipeline instance (loaded only once)
_nlp_pipeline: Optional[Any] = None


def init_model() -> None:
    """
    Initialize the FinBERT sentiment analysis model.

    The model is loaded only once during the
    application lifecycle.
    """

    global _nlp_pipeline

    if _nlp_pipeline is not None:
        return

    _nlp_pipeline = pipeline(
        task="text-classification",
        model=MODEL_NAME,
    )


def analyze_sentiment(text: str) -> Dict[str, Any]:
    """
    Analyze the sentiment of the supplied text.

    Args:
        text:
            Input text.

    Returns:
        Dictionary containing:

        {
            "label": "positive",
            "confidence": 0.97
        }
    """

    global _nlp_pipeline

    if _nlp_pipeline is None:
        init_model()

    if not text or not text.strip():
        return {
            "label": "neutral",
            "confidence": 1.0,
        }

    result = _nlp_pipeline(
        text,
        truncation=True,
        max_length=512,
    )[0]

    return {
        "label": str(result["label"]).lower(),
        "confidence": float(result["score"]),
    }