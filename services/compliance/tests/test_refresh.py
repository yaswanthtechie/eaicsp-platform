from app.services.refresh_service import compare_lists



def test_refresh_detects_changes():

    old = {

        "HAMAS": ["OFAC"]

    }


    new = {

        "HAMAS": ["OFAC"],

        "TEST ENTITY": ["UN"]

    }


    result = compare_lists(
        old,
        new
    )


    assert "TEST ENTITY" in result["added"]