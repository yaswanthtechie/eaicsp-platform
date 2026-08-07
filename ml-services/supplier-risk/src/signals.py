"""
Keyword signal detection module for identifying
financial, operational, and reputational risks.
"""

from typing import Any, Dict, Final, List

# ------------------------------------------------------------------
# Risk Signal Weights
# ------------------------------------------------------------------

SIGNAL_WEIGHTS: Final[Dict[str, int]] = {
    # Financial Risks
    "bankruptcy": 40,
    "insolvency": 35,
    "default": 35,
    "restructuring": 20,
    "layoff": 15,
    "downgrade": 15,

    # Operational Risks
    "strike": 10,
    "recall": 20,
    "disruption": 15,
    "shortage": 10,

    # Reputational Risks
    "fraud": 30,
    "investigation": 25,
    "lawsuit": 20,
    "sanction": 30,
}


def detect_signals(text: str) -> List[Dict[str, Any]]:
    """
    Detect predefined supplier risk keywords.

    Args:
        text:
            Preprocessed lowercase text.

    Returns:
        A list of detected keyword signals.

    Example:
        [
            {
                "keyword": "fraud",
                "weight": 30
            }
        ]
    """

    if not text or not text.strip():
        return []

    detected_signals: List[Dict[str, Any]] = []

    words = set(text.lower().split())

    for keyword, weight in SIGNAL_WEIGHTS.items():

        if keyword in words:
            detected_signals.append(
                {
                    "keyword": keyword,
                    "weight": weight,
                }
            )

    return detected_signals