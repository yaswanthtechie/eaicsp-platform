from datetime import date, timedelta

from app.services.risk_score_service import (
    calculate_country_risk,
    calculate_overall_supplier_risk,
    calculate_recency_score,
    calculate_risk_score,
    parse_date,
)

from app.core.config import (
    CONFIDENCE_WEIGHT,
    SOURCE_WEIGHT,
    RECENCY_WEIGHT,
)


def test_parse_date_iso_format():
    result = parse_date("2026-08-10")

    assert result == date(2026, 8, 10)


def test_parse_date_day_month_year():
    result = parse_date("10-08-2026")

    assert result == date(2026, 8, 10)


def test_parse_date_slash_format():
    result = parse_date("10/08/2026")

    assert result == date(2026, 8, 10)


def test_parse_date_year_slash_month_day():
    result = parse_date("2026/08/10")

    assert result == date(2026, 8, 10)


def test_parse_date_iso_datetime():
    result = parse_date(
        "2026-08-10T12:30:00"
    )

    assert result == date(2026, 8, 10)


def test_parse_date_iso_datetime_z():
    result = parse_date(
        "2026-08-10T12:30:00Z"
    )

    assert result == date(2026, 8, 10)


def test_parse_date_invalid_value():
    result = parse_date("invalid-date")

    assert result is None


def test_parse_date_none():
    result = parse_date(None)

    assert result is None


def test_parse_date_empty_string():
    result = parse_date("")

    assert result is None


def test_parse_date_whitespace():
    result = parse_date("   ")

    assert result is None




def test_recency_score_last_30_days():
    listed_date = (
        date.today() - timedelta(days=10)
    ).isoformat()

    score = calculate_recency_score(
        listed_date
    )

    assert score == 100.0


def test_recency_score_31_to_90_days():
    listed_date = (
        date.today() - timedelta(days=60)
    ).isoformat()

    score = calculate_recency_score(
        listed_date
    )

    assert score == 90.0


def test_recency_score_91_to_180_days():
    listed_date = (
        date.today() - timedelta(days=120)
    ).isoformat()

    score = calculate_recency_score(
        listed_date
    )

    assert score == 75.0


def test_recency_score_181_to_365_days():
    listed_date = (
        date.today() - timedelta(days=300)
    ).isoformat()

    score = calculate_recency_score(
        listed_date
    )

    assert score == 60.0


def test_recency_score_366_to_730_days():
    listed_date = (
        date.today() - timedelta(days=500)
    ).isoformat()

    score = calculate_recency_score(
        listed_date
    )

    assert score == 40.0


def test_recency_score_older_than_730_days():
    listed_date = (
        date.today() - timedelta(days=1000)
    ).isoformat()

    score = calculate_recency_score(
        listed_date
    )

    assert score == 20.0


def test_recency_score_future_date():
    listed_date = (
        date.today() + timedelta(days=30)
    ).isoformat()

    score = calculate_recency_score(
        listed_date
    )

    assert score == 100.0


def test_recency_score_missing_date():
    score = calculate_recency_score(None)
    assert score == 50.0


def test_recency_score_invalid_date():
    score = calculate_recency_score("not-a-date")
    assert score == 50.0


def test_recency_score_is_between_zero_and_hundred():

    test_dates = [
        None,
        "invalid",
        date.today().isoformat(),
        (
            date.today()
            - timedelta(days=1000)
        ).isoformat(),
    ]

    for listed_date in test_dates:

        score = calculate_recency_score(
            listed_date
        )

        assert 0 <= score <= 100




def test_risk_score_returns_required_fields():

    result = calculate_risk_score(
        match_score=100,
        matched_sources=["OFAC"],
        listed_date=date.today().isoformat(),
    )

    assert "risk_score" in result
    assert "risk_factors" in result


def test_risk_score_contains_all_risk_factors():

    result = calculate_risk_score(
        match_score=100,
        matched_sources=["OFAC"],
        listed_date=date.today().isoformat(),
    )

    factors = result["risk_factors"]

    assert "match_confidence" in factors
    assert "source_coverage" in factors
    assert "recency" in factors


def test_risk_score_is_between_zero_and_hundred():

    result = calculate_risk_score(
        match_score=100,
        matched_sources=[
            "OFAC",
            "UN",
            "EU",
        ],
        listed_date=date.today().isoformat(),
    )

    assert 0 <= result["risk_score"] <= 100


def test_perfect_match_all_sources_recent_listing_has_high_risk():

    result = calculate_risk_score(
        match_score=100,
        matched_sources=[
            "OFAC",
            "UN",
            "EU",
        ],
        listed_date=date.today().isoformat(),
    )

    assert result["risk_score"] == 100


def test_zero_match_has_zero_risk():

    result = calculate_risk_score(
        match_score=0,
        matched_sources=[],
        listed_date=None,
    )

    assert (
        result["risk_factors"]
        ["match_confidence"]
        == 0
    )

    assert (
        result["risk_factors"]
        ["source_coverage"]
        == 0
    )

    assert (
    result["risk_factors"]
    ["recency"]
    == 50.0
)

    assert result["risk_score"] == 10


def test_match_confidence_is_limited_to_hundred():

    result = calculate_risk_score(
        match_score=150,
        matched_sources=[],
        listed_date=None,
    )

    assert (
        result["risk_factors"]
        ["match_confidence"]
        == 100
    )


def test_negative_match_score_becomes_zero():

    result = calculate_risk_score(
        match_score=-20,
        matched_sources=[],
        listed_date=None,
    )

    assert (
        result["risk_factors"]
        ["match_confidence"]
        == 0
    )


def test_one_source_has_one_third_source_coverage():

    result = calculate_risk_score(
        match_score=100,
        matched_sources=["OFAC"],
        listed_date=None,
    )

    assert round(
        result["risk_factors"]
        ["source_coverage"],
        2,
    ) == round(
        (1 / 3) * 100,
        2,
    )


def test_two_sources_have_two_thirds_source_coverage():

    result = calculate_risk_score(
        match_score=100,
        matched_sources=[
            "OFAC",
            "UN",
        ],
        listed_date=None,
    )

    assert round(
        result["risk_factors"]
        ["source_coverage"],
        2,
    ) == round(
        (2 / 3) * 100,
        2,
    )


def test_three_sources_have_full_source_coverage():

    result = calculate_risk_score(
        match_score=100,
        matched_sources=[
            "OFAC",
            "UN",
            "EU",
        ],
        listed_date=None,
    )

    assert (
        result["risk_factors"]
        ["source_coverage"]
        == 100
    )


def test_duplicate_sources_do_not_increase_source_score():

    result = calculate_risk_score(
        match_score=100,
        matched_sources=[
            "OFAC",
            "OFAC",
            "OFAC",
        ],
        listed_date=None,
    )

    assert round(
        result["risk_factors"]
        ["source_coverage"],
        2,
    ) == round(
        (1 / 3) * 100,
        2,
    )


def test_source_names_are_case_insensitive():

    result = calculate_risk_score(
        match_score=100,
        matched_sources=[
            "ofac",
            "OFAC",
            "Ofac",
        ],
        listed_date=None,
    )

    assert round(
        result["risk_factors"]
        ["source_coverage"],
        2,
    ) == round(
        (1 / 3) * 100,
        2,
    )


def test_recent_listing_increases_risk():

    recent = calculate_risk_score(
        match_score=90,
        matched_sources=["OFAC"],
        listed_date=date.today().isoformat(),
    )

    old = calculate_risk_score(
        match_score=90,
        matched_sources=["OFAC"],
        listed_date=(
            date.today()
            - timedelta(days=1000)
        ).isoformat(),
    )

    assert (
        recent["risk_score"]
        >
        old["risk_score"]
    )


def test_more_sources_increases_risk():

    one_source = calculate_risk_score(
        match_score=90,
        matched_sources=["OFAC"],
        listed_date=date.today().isoformat(),
    )

    three_sources = calculate_risk_score(
        match_score=90,
        matched_sources=[
            "OFAC",
            "UN",
            "EU",
        ],
        listed_date=date.today().isoformat(),
    )

    assert (
        three_sources["risk_score"]
        >
        one_source["risk_score"]
    )


def test_higher_match_score_increases_risk():

    low_match = calculate_risk_score(
        match_score=60,
        matched_sources=["OFAC"],
        listed_date=date.today().isoformat(),
    )

    high_match = calculate_risk_score(
        match_score=95,
        matched_sources=["OFAC"],
        listed_date=date.today().isoformat(),
    )

    assert (
        high_match["risk_score"]
        >
        low_match["risk_score"]
    )




def test_risk_score_is_integer():

    result = calculate_risk_score(
        match_score=85,
        matched_sources=["OFAC"],
        listed_date=date.today().isoformat(),
    )

    assert isinstance(
        result["risk_score"],
        int,
    )


def test_risk_score_is_not_float():

    result = calculate_risk_score(
        match_score=85,
        matched_sources=["OFAC"],
        listed_date=date.today().isoformat(),
    )

    assert not isinstance(
        result["risk_score"],
        float,
    )


def test_risk_factors_are_numeric():

    result = calculate_risk_score(
        match_score=85,
        matched_sources=["OFAC"],
        listed_date=date.today().isoformat(),
    )

    factors = result["risk_factors"]

    assert isinstance(
        factors["match_confidence"],
        (int, float),
    )

    assert isinstance(
        factors["source_coverage"],
        (int, float),
    )

    assert isinstance(
        factors["recency"],
        (int, float),
    )




def test_india_country_risk():

    score = calculate_country_risk(
        "India"
    )

    assert score == 30.0


def test_usa_country_risk():

    score = calculate_country_risk(
        "USA"
    )

    assert score == 20.0


def test_united_states_country_risk():

    score = calculate_country_risk(
        "United States"
    )

    assert score == 20.0


def test_uk_country_risk():

    score = calculate_country_risk(
        "UK"
    )

    assert score == 20.0


def test_russia_country_risk():

    score = calculate_country_risk(
        "Russia"
    )

    assert score == 70.0


def test_iran_country_risk():

    score = calculate_country_risk(
        "Iran"
    )

    assert score == 90.0


def test_north_korea_country_risk():

    score = calculate_country_risk(
        "North Korea"
    )

    assert score == 100.0


def test_country_risk_is_case_insensitive():

    score = calculate_country_risk(
        "india"
    )

    assert score == 30.0


def test_country_risk_strips_whitespace():

    score = calculate_country_risk(
        "  India  "
    )

    assert score == 30.0


def test_unknown_country_has_neutral_risk():

    score = calculate_country_risk(
        "Unknown Country"
    )

    assert score == 50.0


def test_missing_country_has_neutral_risk():

    score = calculate_country_risk(None)

    assert score == 50.0


def test_empty_country_has_neutral_risk():

    score = calculate_country_risk("")

    assert score == 50.0


def test_country_risk_is_between_zero_and_hundred():

    countries = [
        "India",
        "USA",
        "Russia",
        "Iran",
        "North Korea",
        "Unknown Country",
        None,
    ]

    for country in countries:

        score = calculate_country_risk(
            country
        )

        assert 0 <= score <= 100





def test_overall_supplier_risk_uses_80_20_weight():

    result = calculate_overall_supplier_risk(
        sanctions_score=100,
        country_risk_score=50,
    )

    assert result == 90.0


def test_overall_supplier_risk_with_zero_scores():

    result = calculate_overall_supplier_risk(
        sanctions_score=0,
        country_risk_score=0,
    )

    assert result == 0.0


def test_overall_supplier_risk_with_maximum_scores():

    result = calculate_overall_supplier_risk(
        sanctions_score=100,
        country_risk_score=100,
    )

    assert result == 100.0


def test_overall_supplier_risk_with_example_values():

    result = calculate_overall_supplier_risk(
        sanctions_score=74,
        country_risk_score=50,
    )

    assert result == 69.2


def test_higher_sanctions_risk_increases_overall_risk():

    low = calculate_overall_supplier_risk(
        sanctions_score=40,
        country_risk_score=50,
    )

    high = calculate_overall_supplier_risk(
        sanctions_score=80,
        country_risk_score=50,
    )

    assert high > low


def test_higher_country_risk_increases_overall_risk():

    low = calculate_overall_supplier_risk(
        sanctions_score=70,
        country_risk_score=20,
    )

    high = calculate_overall_supplier_risk(
        sanctions_score=70,
        country_risk_score=80,
    )

    assert high > low


def test_overall_supplier_risk_is_bounded():

    test_cases = [
        (0, 0),
        (100, 100),
        (-20, -10),
        (150, 120),
    ]

    for sanctions_score, country_score in test_cases:

        result = calculate_overall_supplier_risk(
            sanctions_score=sanctions_score,
            country_risk_score=country_score,
        )

        assert 0 <= result <= 100


def test_overall_supplier_risk_is_float():

    result = calculate_overall_supplier_risk(
        sanctions_score=74,
        country_risk_score=50,
    )

    assert isinstance(
        result,
        float,
    )

def test_risk_score_uses_configured_weights():
    result = calculate_risk_score(
        match_score=100,
        matched_sources=["OFAC", "UN", "EU"],
        listed_date=None,
    )

    expected = round(
        100 * CONFIDENCE_WEIGHT
        + 100 * SOURCE_WEIGHT
        + 50 * RECENCY_WEIGHT
    )

    assert result["risk_score"] == expected