import time

import pytest

from fastapi.testclient import TestClient

from app.main import app

from app.services import sanctions_service

from app.services.sanctions_service import (
    screen_entity,
)

from app.services.dedupe_service import (
    deduplicate_entities,
)

from app.schemas.sanctions import (
    SanctionedEntity,
)



client = TestClient(app)




def test_exact_match():

    result = screen_entity(
        "HAMAS"
    )

    assert result["is_flagged"] is True

    assert result["matched_name"] == "HAMAS"

    assert result["match_score"] == 100

    assert len(
        result["matched_lists"]
    ) >= 1




def test_case_insensitive():

    result = screen_entity(
        "hamas"
    )

    assert result["is_flagged"] is True

    assert result["matched_name"] == "HAMAS"

    assert result["match_score"] == 100


# =====================================================
# FIRST OFAC RECORD
# =====================================================

def test_first_ofac_record():

    result = screen_entity(
        "AEROCARIBBEAN AIRLINES"
    )

    assert result["is_flagged"] is True

    assert (
        result["matched_name"]
        == "AEROCARIBBEAN AIRLINES"
    )




def test_acme_fuzzy_match():

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

    try:

        test_key = (
            "ACME CORPORATION LTD"
        )

        sanctions_service.sanction_index[
            test_key
        ] = {

            "name":
                "ACME CORPORATION LTD",

            "sources":
                ["TEST"],

            "aliases":
                [],

            "confidence":
                100,
        }

        sanctions_service.search_keys.append(
            test_key
        )

        sanctions_service.build_prefix_index()

        result = screen_entity(
            "Acme Corp"
        )

        assert result["is_flagged"] is True

        assert result["match_score"] >= 85

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

    assert "OFAC" in (
        record["sources"]
    )

    assert "EU" in (
        record["sources"]
    )

    assert "confidence" in record




def test_un_entity():

    result = screen_entity(
        "ERIC BADEGE"
    )

    assert result["is_flagged"] is True

    assert "UN" in (
        result["matched_lists"]
    )




@pytest.mark.parametrize(
    "name",
    [
        "     ",
        "@@@@@",
        "OpenAI",
        "Random ABC XYZ",
    ],
)
def test_clean_inputs(name):

    response = client.post(
        "/api/v1/compliance/screen",
        json={
            "entity_name": name,
            "entity_type": "supplier",
            "country": "India",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["is_flagged"] is False

    assert data["matched_lists"] == []

    assert data["match_score"] == 0




def test_empty_name_validation():

    response = client.post(
        "/api/v1/compliance/screen",
        json={
            "entity_name": "",
            "entity_type": "supplier",
            "country": "India",
        },
    )

    assert response.status_code == 422




def test_confidence():

    result = screen_entity(
        "HAMAS"
    )

    assert "confidence" in result

    assert result["confidence"] == 1.0




def test_bulk_screen():

    result = sanctions_service.screen_bulk(
        [
            "HAMAS",
            "OpenAI",
        ]
    )

    assert result["count"] == 2

    assert len(
        result["results"]
    ) == 2

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

    assert len(
        result["results"]
    ) == 2

    # -----------------------------------------------
    # Position 0 must belong to OpenAI
    # -----------------------------------------------

    first = result["results"][0]

    assert (
        first["entity_name"]
        == "OpenAI"
    )

    assert (
        first["is_flagged"]
        is False
    )

    # -----------------------------------------------
    # Position 1 must belong to HAMAS
    # -----------------------------------------------

    second = result["results"][1]

    assert (
        second["entity_name"]
        == "HAMAS"
    )

    assert (
        second["is_flagged"]
        is True
    )

    assert (
        second["matched_name"]
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

    assert len(
        result["results"]
    ) == 3

    for item in result["results"]:

        assert item["is_flagged"] is True

        assert item["matched_name"] == "HAMAS"




def test_bulk_50_names_under_100ms():

    names = [
        f"Definitely Not Sanctioned Company {i}"
        for i in range(50)
    ]

    start = time.perf_counter()

    result = sanctions_service.screen_bulk(names)

    elapsed = (
        time.perf_counter() - start
    ) * 1000

    assert result["count"] == 50
    assert elapsed < 100