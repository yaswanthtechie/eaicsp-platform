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
    "bankruptcy": 50,
    "insolvency": 45,
    "default": 40,
    "restructuring": 20,
    "layoff": 25,
    "downgrade": 20,

    # Operational Risks
    "strike": 25,
    "recall": 30,
    "disruption": 20,
    "shortage": 20,
    "delays": 15,
    "shutdown": 35,
    "outage": 25,

    # Reputational/Security Risks
    "fraud": 40,
    "investigation": 25,
    "lawsuit": 25,
    "sanction": 35,
    "cyberattack": 35,
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