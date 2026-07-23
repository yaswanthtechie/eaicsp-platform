from app.services.sanctions_service import (
    load_csv,
    check_name
)

load_csv()


def test_exact_match():

    result = check_name("CIMEX")

    assert result["is_flagged"] is True
    assert result["match_score"] == 100


def test_fuzzy_match():

    result = check_name("Cimex")

    assert result["match_score"] >= 85


def test_clean_name():

    result = check_name("OpenAI")

    assert result["is_flagged"] is False


def test_empty_name():

    result = check_name("")

    assert result["is_flagged"] is False