from app.services.screening_tier_service import (
    calculate_country_risk_tier,
    calculate_transaction_tier,
    calculate_screening_tier,
    get_screening_action,
)



def test_low_country_risk():
    result = calculate_country_risk_tier(20)

    assert result == "LOW"


def test_medium_country_risk():
    result = calculate_country_risk_tier(50)

    assert result == "MEDIUM"


def test_high_country_risk():
    result = calculate_country_risk_tier(90)

    assert result == "HIGH"


def test_low_transaction_value():
    result = calculate_transaction_tier(500000)

    assert result == "LOW"


def test_medium_transaction_value():
    result = calculate_transaction_tier(3000000)

    assert result == "MEDIUM"


def test_high_transaction_value():
    result = calculate_transaction_tier(10000000)

    assert result == "HIGH"


def test_low_screening_tier():
    result = calculate_screening_tier(
        country_risk_score=20,
        transaction_value=500000,
    )

    assert result == "LOW"


def test_medium_screening_tier():
    result = calculate_screening_tier(
        country_risk_score=50,
        transaction_value=500000,
    )

    assert result == "MEDIUM"


def test_high_country_makes_high_screening_tier():
    result = calculate_screening_tier(
        country_risk_score=90,
        transaction_value=500000,
    )

    assert result == "HIGH"


def test_high_transaction_makes_high_screening_tier():
    result = calculate_screening_tier(
        country_risk_score=20,
        transaction_value=10000000,
    )

    assert result == "HIGH"


def test_highest_risk_factor_wins():
    result = calculate_screening_tier(
        country_risk_score=50,
        transaction_value=10000000,
    )

    assert result == "HIGH"


def test_low_boundary():
    result = calculate_screening_tier(
        country_risk_score=39,
        transaction_value=999999,
    )

    assert result == "LOW"


def test_medium_country_boundary():
    result = calculate_screening_tier(
        country_risk_score=40,
        transaction_value=500000,
    )

    assert result == "MEDIUM"


def test_high_country_boundary():
    result = calculate_screening_tier(
        country_risk_score=70,
        transaction_value=500000,
    )

    assert result == "HIGH"






def test_low_screening_action():
    assert get_screening_action("LOW") == "STANDARD_SCREENING"


def test_medium_screening_action():
    assert get_screening_action("MEDIUM") == "ADDITIONAL_COMPLIANCE_REVIEW"


def test_high_screening_action():
    assert (
        get_screening_action("HIGH")
        == "ENHANCED_REVIEW_AND_MANUAL_APPROVAL"
    )