"""
Keyword signal detection module for identifying
financial, operational, and reputational risks.
"""

from typing import Any, Dict, List, Optional, Set
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

    # Mitigation stems and clause boundaries
    mitigation_stems = {"deni", "deny", "avoid", "clear", "resolv", "dismiss"}
    clause_boundaries = {"but", "however", "although", "yet", "while", "though", "nevertheless"}

    words = text.lower().split()

    def is_mitigating_word(w: str) -> bool:
        for stem in mitigation_stems:
            if w.startswith(stem):
                return True
        return False

    # Known inflection variants for standard signal keywords
    keyword_variants: Dict[str, Set[str]] = {
        "bankruptcy": {"bankruptcy", "bankruptcies", "bankrupt"},
        "insolvency": {"insolvency", "insolvent", "insolvencies"},
        "default": {"default", "defaults", "defaulted", "defaulting"},
        "restructuring": {"restructure", "restructures", "restructuring", "restructured"},
        "layoff": {"layoff", "layoffs"},
        "downgrade": {"downgrade", "downgrades", "downgraded", "downgrading"},
        "strike": {"strike", "strikes", "striking"},
        "recall": {"recall", "recalls", "recalled", "recalling"},
        "disruption": {"disrupt", "disrupts", "disruption", "disruptions", "disrupted", "disrupting"},
        "shortage": {"shortage", "shortages"},
        "delays": {"delay", "delays", "delayed", "delaying"},
        "shutdown": {"shutdown", "shutdowns"},
        "outage": {"outage", "outages"},
        "fraud": {"fraud", "frauds", "fraudulent", "fraudulence"},
        "investigation": {"investigate", "investigates", "investigation", "investigations", "investigated", "investigating"},
        "lawsuit": {"lawsuit", "lawsuits"},
        "sanction": {"sanction", "sanctions", "sanctioned", "sanctioning"},
        "cyberattack": {"cyberattack", "cyberattacks"},
    }

    def match_keyword(w: str, kw: str) -> bool:
        # Exact match
        if w == kw:
            return True

        # Predefined inflections
        if kw in keyword_variants and w in keyword_variants[kw]:
            return True

        # Algorithmic inflection matching for custom/dynamic keywords
        # Prevent substring false positives by requiring full token match against inflected forms
        base = kw.rstrip('s')
        if len(base) >= 4 and (w == base or w == kw):
            return True

        # Regular suffix inflections on non-trivial base
        if len(base) >= 4:
            allowed_suffixes = ('s', 'es', 'ed', 'ing')
            for suffix in allowed_suffixes:
                if w == base + suffix:
                    return True
                if base.endswith('e') and w == base[:-1] + suffix:
                    return True

        # y -> ies
        if kw.endswith('y') and len(kw) >= 4 and w == kw[:-1] + 'ies':
            return True

        return False

    for keyword, weight in active_weights.items():
        keyword_detected_unmitigated = False

        for idx, word in enumerate(words):
            if match_keyword(word, keyword):
                # Context disambiguation for ambiguous words
                if keyword == "strike":
                    context_words = set(words[max(0, idx-5):idx+6])
                    valid_context = {"worker", "workers", "union", "unions", "staff", "labor", "labour", "employee", "employees", "walkout"}
                    if not any(cw in context_words for cw in valid_context):
                        continue
                elif keyword == "recall":
                    context_words = set(words[max(0, idx-5):idx+6])
                    valid_context = {"product", "products", "defective", "safety", "vehicle", "vehicles", "part", "parts", "issue"}
                    if not any(cw in context_words for cw in valid_context):
                        continue
                elif keyword == "default":
                    context_words = set(words[max(0, idx-5):idx+6])
                    valid_context = {"loan", "loans", "debt", "debts", "payment", "payments", "credit", "bond", "bonds", "obligation"}
                    if not any(cw in context_words for cw in valid_context):
                        continue

                # Check for mitigation before and after (4 words before, 5 words after)
                is_mitigated = False
                start_idx = max(0, idx - 4)
                end_idx = min(len(words), idx + 6)
                for i in range(start_idx, end_idx):
                    if i != idx and is_mitigating_word(words[i]):
                        span_start = min(idx, i)
                        span_end = max(idx, i)

                        # Do not cross clause boundaries
                        if any(words[s] in clause_boundaries for s in range(span_start + 1, span_end)):
                            continue

                        # Mitigation binds to the nearest risk keyword; do not cross intervening keywords
                        if any(any(match_keyword(words[j], kw) for kw in active_weights) for j in range(span_start + 1, span_end)):
                            continue

                        is_mitigated = True
                        break

                if not is_mitigated:
                    keyword_detected_unmitigated = True
                    break

        if keyword_detected_unmitigated:
            detected_signals.append(
                {
                    "keyword": keyword,
                    "weight": weight,
                }
            )

    return detected_signals
