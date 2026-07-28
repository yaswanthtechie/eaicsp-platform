import pytest

from app.services import sanctions_service
from app.services.sanctions_service import (
    load_csv,
    check_name,
)


@pytest.fixture(scope="module", autouse=True)
def setup():
    load_csv()


def test_exact_match():

    result = check_name("HAMAS")

    assert result["is_flagged"] is True
    assert result["match_score"] == 100
    assert result["matched_name"] == "HAMAS"
    assert "OFAC SDN" in result["matched_lists"]


def test_acme_fuzzy_match():

    original = sanctions_service.sanction_data.copy()

    try:

        sanctions_service.sanction_data["ACME CORPORATION LTD"] = [
            "TEST"
        ]

        result = check_name("Acme Corp")

        assert result["is_flagged"] is True
        assert result["match_score"] >= 85
        assert result["matched_name"] == "ACME CORPORATION LTD"
        assert result["matched_lists"] == ["TEST"]

    finally:

        sanctions_service.sanction_data.clear()
        sanctions_service.sanction_data.update(original)


def test_first_ofac_record():

    result = check_name("AEROCARIBBEAN AIRLINES")

    assert result["is_flagged"] is True
    assert result["matched_name"] == "AEROCARIBBEAN AIRLINES"
    assert "OFAC SDN" in result["matched_lists"]


def test_un_only_entity():

    result = check_name("MOHAMMED ALI")

    assert result["is_flagged"] is True
    assert result["matched_name"] == "MOHAMMED ALI"
    assert result["matched_lists"] == [
        "UN Consolidated"
    ]


def test_duplicate_entity():

    result = check_name("HAMAS")

    assert result["is_flagged"] is True
    assert result["matched_name"] == "HAMAS"
    assert result["match_score"] == 100

    assert "OFAC SDN" in result["matched_lists"]
    assert "UN Consolidated" in result["matched_lists"]


def test_clean_name():

    result = check_name("OpenAI")

    assert result["is_flagged"] is False
    assert result["matched_name"] is None
    assert result["matched_lists"] == []
    assert result["match_score"] == 0


def test_empty_name():

    result = check_name("")

    assert result["is_flagged"] is False
    assert result["matched_name"] is None
    assert result["matched_lists"] == []
    assert result["match_score"] == 0


def test_spaces():

    result = check_name("     ")

    assert result["is_flagged"] is False
    assert result["matched_name"] is None
    assert result["matched_lists"] == []
    assert result["match_score"] == 0

def test_special_characters():

    result = check_name("@@@@@")

    assert result["is_flagged"] is False
    assert result["matched_name"] is None
    assert result["matched_lists"] == []
    assert result["match_score"] == 0



def test_case_insensitive():

    result = check_name("hamas")

    assert result["is_flagged"] is True
    assert result["match_score"] == 100
    assert result["matched_name"] == "HAMAS"