from app.core.config import (
    LOW_COUNTRY_RISK_MAX,
    MEDIUM_COUNTRY_RISK_MAX,
    LOW_TRANSACTION_VALUE_MAX,
    MEDIUM_TRANSACTION_VALUE_MAX,
    LOW_TIER_MATCH_THRESHOLD,
    MEDIUM_TIER_MATCH_THRESHOLD,
    HIGH_TIER_MATCH_THRESHOLD,
)


def calculate_country_risk_tier(
    country_risk_score: float,
) -> str:

    if country_risk_score <= LOW_COUNTRY_RISK_MAX:
        return "LOW"

    if country_risk_score <= MEDIUM_COUNTRY_RISK_MAX:
        return "MEDIUM"

    return "HIGH"


def calculate_transaction_tier(
    transaction_value: float,
) -> str:

    if transaction_value < LOW_TRANSACTION_VALUE_MAX:
        return "LOW"

    if transaction_value <= MEDIUM_TRANSACTION_VALUE_MAX:
        return "MEDIUM"

    return "HIGH"


def calculate_screening_tier(
    country_risk_score: float,
    transaction_value: float,
) -> str:

    country_tier = calculate_country_risk_tier(
        country_risk_score
    )

    transaction_tier = calculate_transaction_tier(
        transaction_value
    )

    tier_priority = {
        "LOW": 1,
        "MEDIUM": 2,
        "HIGH": 3,
    }

    return max(
        country_tier,
        transaction_tier,
        key=lambda tier: tier_priority[tier],
    )

def get_screening_action(screening_tier: str) -> str:
    actions = {
        "LOW": "STANDARD_SCREENING",
        "MEDIUM": "ADDITIONAL_COMPLIANCE_REVIEW",
        "HIGH": "ENHANCED_REVIEW_AND_MANUAL_APPROVAL",
    }

    return actions[screening_tier]

def get_match_threshold(screening_tier: str) -> int:
    thresholds = {
        "LOW": LOW_TIER_MATCH_THRESHOLD,
        "MEDIUM": MEDIUM_TIER_MATCH_THRESHOLD,
        "HIGH": HIGH_TIER_MATCH_THRESHOLD,
    }

    try:
        return thresholds[screening_tier]
    except KeyError:
        raise ValueError(
            f"Unknown screening tier: {screening_tier}"
        )