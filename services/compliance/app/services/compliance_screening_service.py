from sqlalchemy.orm import Session

from app.services.sanctions_service import (
    screen_entity,
    screen_bulk,
)
from app.services.screening_tier_service import (
    calculate_screening_tier,
    get_match_threshold,
    get_screening_action,
)
from app.services.risk_score_service import calculate_country_risk
from app.services.case_service import create_case


def screen_and_open_case(
    db: Session,
    entity_name: str,
    entity_type: str,
    country: str,
    transaction_value: float = 0.0,
) -> dict:
    """
    Perform compliance screening and create or reuse
    a case when the entity is flagged.
    """

    country_risk_score = calculate_country_risk(
        country=country,
    )

    screening_tier = calculate_screening_tier(
        country_risk_score=country_risk_score,
        transaction_value=transaction_value,
    )

    match_threshold = get_match_threshold(
        screening_tier,
    )

    result = screen_entity(
        name=entity_name,
        country=country,
        db=db,
        match_threshold=match_threshold,
    )

    result["entity_name"] = entity_name
    result["entity_type"] = entity_type
    result["country"] = country
    result["transaction_value"] = transaction_value

    result["source"] = result.get(
        "matched_lists",
        [],
    )

    result["country_risk_score"] = (
        country_risk_score
    )

    result["screening_tier"] = screening_tier

    result["enhanced_review_required"] = (
        screening_tier == "HIGH"
    )

    result["screening_action"] = (
        get_screening_action(
            screening_tier,
        )
    )

    if result.get("is_flagged"):
        case = create_case(
            db=db,
            entity_name=entity_name,
            entity_type=entity_type,
            country=country,
            result=result,
        )

        result["case_id"] = case.id
        result["case_number"] = case.case_number
        result["case_status"] = case.status

    return result

def screen_bulk_and_open_cases(
    db: Session,
    entity_names: list[str],
    entity_type: str,
    country: str,
    transaction_value: float = 0.0,
) -> dict:
    """
    Perform bulk compliance screening and create cases
    for flagged entities.
    """

    country_risk_score = calculate_country_risk(
        country=country,
    )

    screening_tier = calculate_screening_tier(
        country_risk_score=country_risk_score,
        transaction_value=transaction_value,
    )

    match_threshold = get_match_threshold(
        screening_tier,
    )

    bulk_result = screen_bulk(
        names=entity_names,
        country=country,
        db=db,
        match_threshold=match_threshold,
    )

    screening_action = get_screening_action(
        screening_tier,
    )

    processed_results = []

    for result in bulk_result["results"]:
        entity_name = result.get(
            "entity_name"
        )

        result["entity_type"] = entity_type
        result["country"] = country
        result["transaction_value"] = (
            transaction_value
        )

        result["source"] = result.get(
            "matched_lists",
            [],
        )

        result["country_risk_score"] = (
            country_risk_score
        )

        result["screening_tier"] = (
            screening_tier
        )

        result["enhanced_review_required"] = (
            screening_tier == "HIGH"
        )

        result["screening_action"] = (
            screening_action
        )

        if result.get("is_flagged"):
            case = create_case(
                db=db,
                entity_name=entity_name,
                entity_type=entity_type,
                country=country,
                result=result,
            )

            result["case_id"] = case.id
            result["case_number"] = (
                case.case_number
            )
            result["case_status"] = case.status

        processed_results.append(result)

    return {
        "entity_type": entity_type,
        "country": country,
        "results": processed_results,
        "count": bulk_result["count"],
        "total_duration_ms": bulk_result[
            "total_duration_ms"
        ],
    }