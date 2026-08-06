import pytest


from app.services import sanctions_service


from app.services.sanctions_service import (

    load_all_sanctions,

    screen_entity,

)



@pytest.fixture(
    scope="module",
    autouse=True
)
def setup():

    load_all_sanctions()





def test_exact_match():


    result = screen_entity(
        "HAMAS"
    )


    assert result["is_flagged"] is True

    assert result["match_score"] == 100

    assert result["matched_name"] == "HAMAS"

    assert len(result["matched_lists"]) > 0





def test_acme_fuzzy_match():


    original = sanctions_service.sanction_index.copy()


    try:


        sanctions_service.sanction_index[
            "ACME CORPORATION LTD"
        ] = {


            "name":
                "ACME CORPORATION LTD",


            "sources":
                [
                    "TEST"
                ],


            "aliases":
                []

        }


        sanctions_service.search_keys.append(

            "ACME CORPORATION LTD"

        )



        result = screen_entity(

            "Acme Corp"

        )


        assert result["is_flagged"] is True

        assert result["match_score"] >= 85

        assert result["matched_name"] == "ACME CORPORATION LTD"

        assert "TEST" in result["matched_lists"]



    finally:


        sanctions_service.sanction_index.clear()

        sanctions_service.sanction_index.update(
            original
        )





def test_first_ofac_record():


    result = screen_entity(

        "AEROCARIBBEAN AIRLINES"

    )


    assert result["is_flagged"] is True

    assert result["matched_name"] == "AEROCARIBBEAN AIRLINES"





def test_un_only_entity():


    result = screen_entity(

        "ERIC BADEGE"

    )


    assert result["is_flagged"] is True

    assert result["matched_name"] == "ERIC BADEGE"

    assert "UN" in result["matched_lists"]





def test_duplicate_entity():


    result = screen_entity(

        "HAMAS"

    )


    assert result["is_flagged"] is True


    assert result["matched_name"] == "HAMAS"


    assert result["match_score"] == 100


    assert len(result["matched_lists"]) >= 2





def test_clean_name():


    result = screen_entity(

        "OpenAI"

    )


    assert result["is_flagged"] is False


    assert result["match_score"] == 0





def test_empty_name():


    result = screen_entity(

        ""

    )


    assert result["is_flagged"] is False


    assert result["match_score"] == 0





def test_spaces():


    result = screen_entity(

        "     "

    )


    assert result["is_flagged"] is False


    assert result["match_score"] == 0





def test_special_characters():


    result = screen_entity(

        "@@@@@"

    )


    assert result["is_flagged"] is False





def test_case_insensitive():


    result = screen_entity(

        "hamas"

    )


    assert result["is_flagged"] is True


    assert result["match_score"] == 100





def test_confidence_exists():


    result = screen_entity(

        "HAMAS"

    )


    assert "confidence" in result


    assert result["confidence"] == 1.0





def test_bulk_screen():


    results = sanctions_service.screen_bulk(

        [

            "HAMAS",

            "OpenAI"

        ]

    )


    assert results["count"] == 2


    assert len(results["results"]) == 2


    assert results["results"][0]["is_flagged"] is True


    assert results["results"][1]["is_flagged"] is False