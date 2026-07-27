import pytest

from app.services.sanctions_service import (
    load_csv,
    check_name,
)




@pytest.fixture(scope="module", autouse=True)
def setup_sanctions():

    load_csv()




def test_exact_match():

    result = check_name("HAMAS")

    assert result["is_flagged"] is True
    assert result["match_score"] == 100
    assert result["matched_name"] == "HAMAS"
    assert "OFAC SDN" in result["matched_lists"]



def test_fuzzy_match():

    result = check_name("ANGLO-CARIBBEAN  LTD")

    assert result["match_score"] >= 85
    assert result["is_flagged"] is True



def test_clean_name():

    result = check_name("OpenAI")

    assert result["is_flagged"] is False
    assert result["match_score"] < 85


# -------------------------------------------------
# Empty Name
# -------------------------------------------------

def test_empty_name():

    result = check_name("")

    assert result["is_flagged"] is False
    assert result["match_score"] == 0
    assert result["matched_name"] == ""



def test_spaces():

    result = check_name("      ")

    assert result["is_flagged"] is False
    assert result["match_score"] == 0




def test_special_characters():

    result = check_name("@@@@@")

    assert result["is_flagged"] is False




def test_long_name():

    result = check_name("A" * 500)

    assert result["is_flagged"] is False