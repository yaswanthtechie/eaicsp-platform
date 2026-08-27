"""
Keyword signal detection module for identifying
financial, operational, and reputational risks.
"""

from typing import Any, Dict, List, Optional
from src.config import DEFAULT_SIGNAL_WEIGHTS, get_settings

# Alias for backward-compatibility with tests / existing callers
SIGNAL_WEIGHTS = DEFAULT_SIGNAL_WEIGHTS


def detect_signals(
    text: str,
    weights: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """
    Detect supplier risk keywords using configurable weights.

    Args:
        text:
            Preprocessed lowercase text.
        weights:
            Optional dictionary of keyword-to-weight mappings.
            If None, uses active configuration from settings.

    Returns:
        A list of detected keyword signals with their weights.

    Example:
        [
            {
                "keyword": "fraud",
                "weight": 40
            }
        ]
    """
    if not text or not text.strip():
        return []

    active_weights = weights if weights is not None else get_settings().signal_weights
    detected_signals: List[Dict[str, Any]] = []
    words = set(text.lower().split())

    for keyword, weight in active_weights.items():
        if keyword in words:
            detected_signals.append(
                {
                    "keyword": keyword,
                    "weight": weight,
                }
            )

    return detected_signals