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

    # Mitigation words that negate following risks
    mitigators = {"denies", "avoids", "cleared", "resolved", "dismissed"}

    words = text.lower().split()

    for keyword, weight in SIGNAL_WEIGHTS.items():
        base_keyword = keyword.rstrip('s')

        # Find all occurrences of the keyword in words
        keyword_detected_unmitigated = False

        for idx, word in enumerate(words):
            if word == keyword or word.startswith(base_keyword):
                # Check if this specific occurrence is mitigated
                is_mitigated = False
                start_idx = max(0, idx - 4)
                for i in range(start_idx, idx):
                    if words[i] in mitigators:
                        is_mitigated = True
                        break

                if not is_mitigated:
                    keyword_detected_unmitigated = True
                    break # We found at least one unmitigated occurrence, no need to check others

        if keyword_detected_unmitigated:
            detected_signals.append(
                {
                    "keyword": keyword,
                    "weight": weight,
                }
            )

    return detected_signals
