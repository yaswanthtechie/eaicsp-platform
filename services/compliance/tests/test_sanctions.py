import time

import pytest

from app.schemas.sanctions import SanctionedEntity
from app.services import sanctions_service
from app.services.dedupe_service import deduplicate_entities
from app.services.sanctions_service import screen_entity




def test_exact_match():
    result = screen_entity("HAMAS")

    assert result["is_flagged"] is True
    assert result["matched_name"] == "HAMAS"
    assert result["match_score"] == 100
    assert len(result["matched_lists"]) >= 1


def test_case_insensitive_match():
    result = screen_entity("hamas")

    assert result["is_flagged"] is True
    assert result["matched_name"] == "HAMAS"
    assert result["match_score"] == 100


def test_first_ofac_record_is_not_skipped():
    result = screen_entity(
        "AEROCARIBBEAN AIRLINES"
    )

    assert result["is_flagged"] is True
    assert (
        result["matched_name"]
        == "AEROCARIBBEAN AIRLINES"
    )


def test_un_entity():
    result = screen_entity(
        "ERIC BADEGE"
    )

    assert result["is_flagged"] is True
    assert "UN" in result["matched_lists"]


def test_clean_entity():
    result = screen_entity(
        "XYZ UNIQUE COMPANY 123"
    )

    assert result["is_flagged"] is False
    assert result["matched_name"] is None
    assert result["matched_lists"] == []
    assert result["matched_count"] == 0
    assert result["match_score"] == 0
    assert result["confidence"] == 0
    assert result["risk_score"] == 0





def test_empty_name_raises_error():
    with pytest.raises(ValueError):
        screen_entity("")


def test_whitespace_name_raises_error():
    with pytest.raises(ValueError):
        screen_entity("     ")


def test_none_name_raises_error():
    with pytest.raises(ValueError):
        screen_entity(None)


def test_non_string_name_raises_error():
    with pytest.raises(ValueError):
        screen_entity(123)


def test_special_character_only_name_is_clean():
    result = screen_entity("@@@@@")

    assert result["is_flagged"] is False
    assert result["matched_name"] is None
    assert result["matched_lists"] == []
    assert result["matched_count"] == 0
    assert result["match_score"] == 0
    assert result["confidence"] == 0
    assert result["risk_score"] == 0




def test_fuzzy_match():
    original_index = (
        sanctions_service.sanction_index.copy()
    )

    original_keys = (
        sanctions_service.search_keys.copy()
    )

    original_prefix_index = {
        key: values.copy()
        for key, values
        in sanctions_service.prefix_index.items()
    }

    original_two_char_index = {
        key: values.copy()
        for key, values
        in sanctions_service.two_char_index.items()
    }

    original_first_char_index = {
        key: values.copy()
        for key, values
        in sanctions_service.first_char_index.items()
    }

    try:
        test_key = (
            "ACME CORPORATION LTD"
        )

        sanctions_service.sanction_index[
            test_key
        ] = {
            "name": test_key,
            "sources": ["TEST"],
            "aliases": [],
            "confidence": 100,
            "listed_date": None,
        }

        sanctions_service.search_keys.append(
            test_key
        )

        sanctions_service.build_prefix_index()

        result = screen_entity(
            "Acme Corp"
        )

        assert result["is_flagged"] is True

        assert (
            result["match_score"]
            >= 85
        )

        assert (
            result["matched_name"]
            == "ACME CORPORATION LTD"
        )

        assert "TEST" in (
            result["matched_lists"]
        )

    finally:
        sanctions_service.sanction_index.clear()

        sanctions_service.sanction_index.update(
            original_index
        )

        sanctions_service.search_keys.clear()

        sanctions_service.search_keys.extend(
            original_keys
        )

        sanctions_service.prefix_index.clear()

        sanctions_service.prefix_index.update(
            original_prefix_index
        )

        sanctions_service.two_char_index.clear()

        sanctions_service.two_char_index.update(
            original_two_char_index
        )

        sanctions_service.first_char_index.clear()

        sanctions_service.first_char_index.update(
            original_first_char_index
        )




def test_cross_source_deduplication():
    entities = [
        SanctionedEntity(
            name="ACME CORPORATION",
            aliases=[],
            source="OFAC",
        ),
        SanctionedEntity(
            name="ACME CORP",
            aliases=[],
            source="EU",
        ),
    ]

    merged = deduplicate_entities(
        entities,
        threshold=85,
    )

    assert len(merged) == 1

    record = list(
        merged.values()
    )[0]

    assert "OFAC" in record["sources"]
    assert "EU" in record["sources"]
    assert "confidence" in record





def test_confidence_exists():
    result = screen_entity("HAMAS")

    assert "confidence" in result


def test_confidence_is_between_zero_and_one():
    result = screen_entity("HAMAS")

    assert 0 <= result["confidence"] <= 1


def test_exact_match_has_full_confidence():
    result = screen_entity("HAMAS")

    assert result["confidence"] == 1.0


def test_clean_entity_has_zero_confidence():
    result = screen_entity(
        "XYZ UNIQUE COMPANY 123"
    )

    assert result["confidence"] == 0.0




def test_matched_lists_are_returned():
    result = screen_entity("HAMAS")

    assert isinstance(
        result["matched_lists"],
        list,
    )


def test_matched_lists_contain_valid_sources():
    result = screen_entity("HAMAS")

    valid_sources = {
        "OFAC",
        "UN",
        "EU",
        "TEST",
    }

    for source in result["matched_lists"]:
        assert source in valid_sources


def test_matched_count_matches_sources():
    result = screen_entity("HAMAS")

    assert (
        result["matched_count"]
        == len(result["matched_lists"])
    )




def test_screening_result_contains_risk_score():
    result = screen_entity("HAMAS")

    assert "risk_score" in result


def test_screening_result_contains_risk_factors():
    result = screen_entity("HAMAS")

    assert "risk_factors" in result


def test_screening_risk_score_is_valid():
    result = screen_entity("HAMAS")

    assert 0 <= result["risk_score"] <= 100


def test_clean_entity_has_zero_risk():
    result = screen_entity(
        "XYZ UNIQUE COMPANY 123"
    )

    assert result["is_flagged"] is False
    assert result["risk_score"] == 0


def test_risk_factors_are_returned_for_match():
    result = screen_entity("HAMAS")

    factors = result["risk_factors"]

    assert "match_confidence" in factors
    assert "source_coverage" in factors
    assert "recency" in factors





def test_bulk_screen():
    result = sanctions_service.screen_bulk(
        [
            "HAMAS",
            "OpenAI",
        ]
    )

    assert result["count"] == 2
    assert len(result["results"]) == 2

    assert (
        result["results"][0]["entity_name"]
        == "HAMAS"
    )

    assert (
        result["results"][0]["is_flagged"]
        is True
    )

    assert (
        result["results"][1]["entity_name"]
        == "OpenAI"
    )

    assert (
        result["results"][1]["is_flagged"]
        is False
    )


def test_bulk_preserves_input_order():
    names = [
        "OpenAI",
        "HAMAS",
    ]

    result = sanctions_service.screen_bulk(
        names
    )

    assert result["count"] == 2

    assert (
        result["results"][0]["entity_name"]
        == "OpenAI"
    )

    assert (
        result["results"][1]["entity_name"]
        == "HAMAS"
    )


def test_bulk_duplicate_names():
    result = sanctions_service.screen_bulk(
        [
            "HAMAS",
            "HAMAS",
            "hamas",
        ]
    )

    assert result["count"] == 3
    assert len(result["results"]) == 3

    for item in result["results"]:
        assert item["is_flagged"] is True

        assert (
            item["matched_name"]
            == "HAMAS"
        )

        assert (
            0 <= item["risk_score"] <= 100
        )


def test_bulk_empty_list_raises_error():
    with pytest.raises(ValueError):
        sanctions_service.screen_bulk([])


def test_bulk_none_raises_error():
    with pytest.raises(ValueError):
        sanctions_service.screen_bulk(None)


def test_bulk_non_list_raises_error():
    with pytest.raises(ValueError):
        sanctions_service.screen_bulk(
            "HAMAS"
        )


def test_bulk_contains_blank_name_raises_error():
    with pytest.raises(ValueError):
        sanctions_service.screen_bulk(
            [
                "HAMAS",
                "",
            ]
        )


def test_bulk_contains_whitespace_name_raises_error():
    with pytest.raises(ValueError):
        sanctions_service.screen_bulk(
            [
                "HAMAS",
                "     ",
            ]
        )




def test_bulk_50_names_under_100ms():
    names = [
        f"Definitely Not Sanctioned Company {i}"
        for i in range(50)
    ]

    start = time.perf_counter()

    result = sanctions_service.screen_bulk(
        names
    )

    elapsed = (
        time.perf_counter() - start
    ) * 1000

    assert result["count"] == 50

    assert elapsed < 100


def test_bulk_screen_500_entities():
    entities = [
        "HAMAS",
        "OpenAI",
        "AEROCARIBBEAN AIRLINES",
        "ERIC BADEGE",
        "Random Company",
    ]

    entities.extend(
        f"Test Company {i}"
        for i in range(1, 496)
    )

    assert len(entities) == 500
    assert len(set(entities)) == 500

    start = time.perf_counter()

    result = sanctions_service.screen_bulk(
        entities
    )

    duration_ms = (
        time.perf_counter() - start
    ) * 1000

    print(
        f"\nBulk screening 500 entities "
        f"took {duration_ms:.2f} ms"
    )

    assert result["count"] == 500

    assert len(
        result["results"]
    ) == 500



def test_bulk_flagged_results_have_risk_score():
    result = sanctions_service.screen_bulk(
        [
            "HAMAS",
            "AEROCARIBBEAN AIRLINES",
        ]
    )

    for item in result["results"]:
        assert "risk_score" in item
        assert 0 <= item["risk_score"] <= 100


def test_bulk_clean_result_has_zero_risk():
    result = sanctions_service.screen_bulk(
        [
            "OpenAI",
        ]
    )

    item = result["results"][0]

    assert item["is_flagged"] is False
    assert item["risk_score"] == 0




def test_flagged_result_contains_required_fields():
    result = screen_entity("HAMAS")

    required_fields = {
        "entity_name",
        "is_flagged",
        "matched_lists",
        "matched_count",
        "matched_name",
        "aliases",
        "match_score",
        "confidence",
        "risk_score",
        "risk_factors",
        "duration_ms",
        "source",
    }

    for field in required_fields:
        assert field in result


def test_clean_result_contains_required_fields():
    result = screen_entity(
        "XYZ UNIQUE COMPANY 123"
    )

    required_fields = {
        "entity_name",
        "is_flagged",
        "matched_lists",
        "matched_count",
        "matched_name",
        "aliases",
        "match_score",
        "confidence",
        "risk_score",
        "risk_factors",
        "duration_ms",
        "source",
    }

    for field in required_fields:
        assert field in result


def test_flagged_result_duration_is_non_negative():
    result = screen_entity("HAMAS")

    assert result["duration_ms"] >= 0


def test_clean_result_duration_is_non_negative():
    result = screen_entity(
        "XYZ UNIQUE COMPANY 123"
    )

    assert result["duration_ms"] >= 0




def test_ofac_missing_listing_date_is_handled():
    result = sanctions_service.screen_entity(
        "AEROCARIBBEAN AIRLINES"
    )

    assert result["is_flagged"] is True
    assert result["risk_factors"]["recency"] == 0
    assert result["risk_factors"]["match_confidence"] > 0
    assert result["risk_factors"]["source_coverage"] > 0