from typing import Any


REGULATORY_RULES: dict[str, list[dict[str, Any]]] = {
    "INDIA": [
        {
            "rule_code": "IND-SANCTIONS",
            "rule_name": "Sanctions Screening",
            "description": "Supplier must pass applicable sanctions screening.",
        },
        {
            "rule_code": "IND-KYC",
            "rule_name": "KYC Verification",
            "description": "Supplier identity and required KYC information must be verified.",
        },
        {
            "rule_code": "IND-DOCUMENTATION",
            "rule_name": "Supplier Documentation",
            "description": "Required supplier documentation must be available.",
        },
    ],
    "USA": [
        {
            "rule_code": "US-SANCTIONS",
            "rule_name": "US Sanctions Screening",
            "description": "Supplier must pass applicable US sanctions screening.",
        },
        {
            "rule_code": "US-KYC",
            "rule_name": "US KYC Verification",
            "description": "Supplier identity and required KYC information must be verified.",
        },
        {
            "rule_code": "US-REPORTING",
            "rule_name": "Regulatory Reporting",
            "description": "Applicable US regulatory reporting requirements must be considered.",
        },
    ],
}


def get_regulatory_rules(
    country: str,
) -> list[dict[str, Any]]:
    normalized_country = country.strip().upper()

    return REGULATORY_RULES.get(
        normalized_country,
        [],
    )


def evaluate_regulatory_rules(
    country: str,
    sanctions_cleared: bool,
    kyc_verified: bool,
    documents_complete: bool,
    reporting_compliant: bool = True,
) -> dict[str, Any]:
    normalized_country = country.strip().upper()

    rules = get_regulatory_rules(normalized_country)

    if not rules:
        return {
            "country": normalized_country,
            "overall_status": "REVIEW",
            "rules": [],
            "reason": "No regulatory rules are configured for this country.",
        }

    results: list[dict[str, Any]] = []

    for rule in rules:
        code = rule["rule_code"]

        if code.endswith("SANCTIONS"):
            status = "PASSED" if sanctions_cleared else "FAILED"

        elif code.endswith("KYC"):
            status = "PASSED" if kyc_verified else "REVIEW"

        elif code.endswith("DOCUMENTATION"):
            status = "PASSED" if documents_complete else "REVIEW"

        elif code.endswith("REPORTING"):
            status = "PASSED" if reporting_compliant else "REVIEW"

        else:
            status = "REVIEW"

        results.append(
            {
                "rule_code": code,
                "rule_name": rule["rule_name"],
                "status": status,
            }
        )

    statuses = {
        result["status"]
        for result in results
    }

    if "FAILED" in statuses:
        overall_status = "FAILED"
    elif "REVIEW" in statuses:
        overall_status = "REVIEW"
    else:
        overall_status = "PASSED"

    passed_count = sum(
        result["status"] == "PASSED"
        for result in results
    )

    failed_count = sum(
        result["status"] == "FAILED"
        for result in results
    )

    review_count = sum(
        result["status"] == "REVIEW"
        for result in results
    )

    return {
        "country": normalized_country,
        "overall_status": overall_status,
        "rules": results,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "review_count": review_count,
    }