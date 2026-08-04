"""
Keyword signal detection module for identifying financial, operational, and reputational risks.
"""
from typing import Any, Dict, List

# Keyword weights as defined in requirements
SIGNAL_WEIGHTS = {
    # Financial
    "bankruptcy": 40,
    "insolvency": 35,
    "default": 35,
    "restructuring": 20,
    "layoff": 15,
    "downgrade": 15,
    # Operational
    "strike": 10,
    "recall": 20,
    "disruption": 15,
    "shortage": 10,
    # Reputational
    "fraud": 30,
    "investigation": 25,
    "lawsuit": 20,
    "sanction": 30
}

def detect_signals(text: str) -> List[Dict[str, Any]]:
    """
    Detect risk keywords in the given text and return their weights.
    
    Args:
        text (str): The preprocessed (lowercase, no punctuation) input text.
        
    Returns:
        List[Dict[str, Any]]: A list of dictionaries representing the detected signals.
            Example: [{"keyword": "bankruptcy", "weight": 40}]
    """
    detected_signals = []
    
    # Split text into words to do word-level matching
    words = set(text.split())
    
    for keyword, weight in SIGNAL_WEIGHTS.items():
        if keyword in words:
            detected_signals.append({
                "keyword": keyword,
                "weight": weight
            })
            
    return detected_signals
