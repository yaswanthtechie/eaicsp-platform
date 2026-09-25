from collections import Counter
import re

from app.services.three_way_match_service import three_way_matches


# ============================================================
# RESOLUTION ACTION PATTERNS
# ============================================================

RESOLUTION_PATTERNS = {
    "correct_invoice": (
        "correct invoice",
        "corrected invoice",
        "invoice correction",
        "invoice corrected",
        "revised invoice",
        "invoice revised",
        "invoice updated",
        "update invoice",
    ),
    "credit_note": (
        "credit note",
        "credit memo",
        "credit issued",
        "credit adjustment",
    ),
    "accept_exception": (
        "accept exception",
        "exception accepted",
        "exception approved",
        "accept the exception",
        "accepted the exception",
        "waived",
        "waiver",
    ),
    "escalate_review": (
        "escalate",
        "escalated",
        "further review",
        "additional review",
        "manual review",
        "review required",
        "compliance review",
    ),
}


# ============================================================
# TEXT HELPERS
# ============================================================

def _normalize_text(value: str) -> str:
    """
    Normalize resolution text for pattern matching.
    """
    value = value.strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value


def _classify_resolution(reason: str) -> str | None:
    """
    Convert a historical free-text resolution reason
    into a normalized resolution action.

    Returns None when the historical reason cannot
    be classified reliably.
    """
    normalized_reason = _normalize_text(reason)

    for action, patterns in RESOLUTION_PATTERNS.items():
        for pattern in patterns:
            if pattern in normalized_reason:
                return action

    return None


# ============================================================
# HISTORICAL CASE ANALYSIS
# ============================================================

def _get_historical_resolutions(
    current_match_id: str,
    discrepancy_type: str,
) -> list[str]:
    """
    Find previously resolved three-way-match disputes
    having the same discrepancy type.

    The current match is excluded.
    Only resolved/matched historical cases with a
    valid resolution reason are considered.
    """

    historical_actions: list[str] = []

    for match in three_way_matches.values():
        # Never use the current dispute as historical evidence.
        if match.get("match_id") == current_match_id:
            continue

        # Only resolved matches are useful for learning
        # from previous resolution decisions.
        if match.get("status") != "matched":
            continue

        discrepancies = match.get("discrepancies", [])

        if discrepancy_type not in discrepancies:
            continue

        resolution = match.get("resolution")

        if not isinstance(resolution, dict):
            continue

        reason = resolution.get("reason")

        if not isinstance(reason, str) or not reason.strip():
            continue

        action = _classify_resolution(reason)

        if action is not None:
            historical_actions.append(action)

    return historical_actions


# ============================================================
# SUGGESTION GENERATION
# ============================================================

def _build_suggestion(
    discrepancy_type: str,
    historical_actions: list[str],
) -> dict:
    """
    Build one resolution suggestion for a discrepancy type.
    """

    if not historical_actions:
        return {
            "discrepancy_type": discrepancy_type,
            "suggested_action": None,
            "historical_case_count": 0,
            "supporting_case_count": 0,
            "rationale": (
                "No classified historical resolution pattern "
                "was found for this discrepancy type."
            ),
        }

    action_counts = Counter(historical_actions)

    suggested_action, supporting_case_count = (
        action_counts.most_common(1)[0]
    )

    historical_case_count = len(historical_actions)

    action_descriptions = {
        "correct_invoice": (
            "Historical cases most commonly resulted in "
            "requesting a corrected or revised invoice."
        ),
        "credit_note": (
            "Historical cases most commonly resulted in "
            "requesting or issuing a credit note."
        ),
        "accept_exception": (
            "Historical cases most commonly resulted in "
            "accepting or approving the exception."
        ),
        "escalate_review": (
            "Historical cases most commonly resulted in "
            "additional or manual review."
        ),
    }

    return {
        "discrepancy_type": discrepancy_type,
        "suggested_action": suggested_action,
        "historical_case_count": historical_case_count,
        "supporting_case_count": supporting_case_count,
        "rationale": action_descriptions[suggested_action],
    }


# ============================================================
# PUBLIC SERVICE FUNCTION
# ============================================================

def get_dispute_resolution_suggestions(
    supplier_id: str,
    invoice_number: str,
) -> dict:
    """
    Generate automated resolution suggestions for an
    existing three-way-match discrepancy.

    This function is READ-ONLY.

    It does not:
        - change the match status
        - change the P2P state
        - resolve the dispute
        - approve payment

    It only analyzes historical resolved disputes and
    returns suggested resolution actions.
    """

    match_key = (supplier_id, invoice_number)

    match = three_way_matches.get(match_key)

    if match is None:
        raise KeyError(
            "Three-way match not found."
        )

    if match.get("status") != "discrepancy":
        raise ValueError(
            "Resolution suggestions are available only "
            "for unresolved discrepancies."
        )

    discrepancy_types = match.get("discrepancies", [])

    suggestions = []

    for discrepancy_type in discrepancy_types:
        historical_actions = _get_historical_resolutions(
            current_match_id=match["match_id"],
            discrepancy_type=discrepancy_type,
        )

        suggestion = _build_suggestion(
            discrepancy_type=discrepancy_type,
            historical_actions=historical_actions,
        )

        suggestions.append(suggestion)

    return {
        "match_id": match["match_id"],
        "supplier_id": supplier_id,
        "invoice_number": invoice_number,
        "suggestions": suggestions,
    }