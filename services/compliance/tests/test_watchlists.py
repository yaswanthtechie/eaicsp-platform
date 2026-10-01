from app.services.sanctions_service import screen_entity
from app.services.risk_score_service import calculate_risk_score


def test_internal_watchlist_exact_match():
    result = screen_entity("ACME TRADING LTD")

    assert result["is_flagged"] is True
    assert result["matched_name"] == "ACME TRADING LTD"
    assert "INTERNAL_WATCHLIST" in result["matched_lists"]
    assert result["matched_count"] == 1
    assert result["source"] == ["INTERNAL_WATCHLIST"]


def test_pep_exact_match():
    result = screen_entity("MARIA GARCIA")

    assert result["is_flagged"] is True
    assert result["matched_name"] == "MARIA GARCIA"
    assert "PEP" in result["matched_lists"]
    assert result["matched_count"] == 1
    assert result["source"] == ["PEP"]


def test_cross_source_deduplication():
    result = screen_entity("JOHN SMITH")

    assert result["is_flagged"] is True
    assert result["matched_name"] == "JOHN SMITH"
    assert result["matched_count"] == 2

    assert set(result["matched_lists"]) == {
        "INTERNAL_WATCHLIST",
        "PEP",
    }

    assert set(result["source"]) == {
        "INTERNAL_WATCHLIST",
        "PEP",
    }


def test_five_sources_have_full_source_coverage():
    result = calculate_risk_score(
        match_score=100,
        matched_sources=[
            "OFAC",
            "UN",
            "EU",
            "INTERNAL_WATCHLIST",
            "PEP",
        ],
        listed_date=None,
    )

    assert result["risk_factors"]["source_coverage"] == 100


def test_internal_watchlist_case_insensitive():
    result = screen_entity("acme trading ltd")

    assert result["is_flagged"] is True
    assert result["matched_name"] == "ACME TRADING LTD"
    assert "INTERNAL_WATCHLIST" in result["matched_lists"]


def test_pep_case_insensitive():
    result = screen_entity("maria garcia")

    assert result["is_flagged"] is True
    assert result["matched_name"] == "MARIA GARCIA"
    assert "PEP" in result["matched_lists"]


