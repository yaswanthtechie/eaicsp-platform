
from app.services.regulatory_rules_service import (
    evaluate_regulatory_rules,
    get_regulatory_rules,
)

def test_india_gets_india_rules():
    rules = get_regulatory_rules("India")

    codes = {rule["rule_code"] for rule in rules}

    assert "IND-SANCTIONS" in codes
    assert "IND-KYC" in codes
    assert "US-KYC" not in codes


def test_usa_gets_usa_rules():
    rules = get_regulatory_rules("USA")

    codes = {rule["rule_code"] for rule in rules}

    assert "US-SANCTIONS" in codes
    assert "US-KYC" in codes
    assert "IND-KYC" not in codes


def test_unknown_country_returns_no_rules():
    rules = get_regulatory_rules("UNKNOWN")

    assert rules == []





def test_india_all_rules_pass():
    result = evaluate_regulatory_rules(
        country="India",
        sanctions_cleared=True,
        kyc_verified=True,
        documents_complete=True,
    )

    assert result["overall_status"] == "PASSED"

    statuses = {
        rule["rule_code"]: rule["status"]
        for rule in result["rules"]
    }

    assert statuses["IND-SANCTIONS"] == "PASSED"
    assert statuses["IND-KYC"] == "PASSED"
    assert statuses["IND-DOCUMENTATION"] == "PASSED"


def test_india_sanctions_failure():
    result = evaluate_regulatory_rules(
        country="India",
        sanctions_cleared=False,
        kyc_verified=True,
        documents_complete=True,
    )

    assert result["overall_status"] == "FAILED"


def test_india_kyc_requires_review():
    result = evaluate_regulatory_rules(
        country="India",
        sanctions_cleared=True,
        kyc_verified=False,
        documents_complete=True,
    )

    assert result["overall_status"] == "REVIEW"

def test_jurisdictions_use_different_rules():
    india = get_regulatory_rules("India")
    usa = get_regulatory_rules("USA")

    india_codes = {
        rule["rule_code"]
        for rule in india
    }

    usa_codes = {
        rule["rule_code"]
        for rule in usa
    }

    assert india_codes != usa_codes
    assert india_codes.isdisjoint(usa_codes)


def test_india_documents_incomplete_requires_review():
    result = evaluate_regulatory_rules(
        country="India",
        sanctions_cleared=True,
        kyc_verified=True,
        documents_complete=False,
    )

    assert result["overall_status"] == "REVIEW"

    statuses = {
        rule["rule_code"]: rule["status"]
        for rule in result["rules"]
    }

    assert statuses["IND-DOCUMENTATION"] == "REVIEW"


def test_usa_all_rules_pass():
    result = evaluate_regulatory_rules(
        country="USA",
        sanctions_cleared=True,
        kyc_verified=True,
        documents_complete=True,
        reporting_compliant=True,
    )

    assert result["overall_status"] == "PASSED"

    statuses = {
        rule["rule_code"]: rule["status"]
        for rule in result["rules"]
    }

    assert statuses["US-SANCTIONS"] == "PASSED"
    assert statuses["US-KYC"] == "PASSED"
    assert statuses["US-REPORTING"] == "PASSED"

def test_unknown_country_requires_review():
    result = evaluate_regulatory_rules(
        country="UNKNOWN",
        sanctions_cleared=True,
        kyc_verified=True,
        documents_complete=True,
    )

    assert result["overall_status"] == "REVIEW"