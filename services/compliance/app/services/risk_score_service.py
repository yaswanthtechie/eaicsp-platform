
from datetime import date, datetime

from app.core.config import (
    CONFIDENCE_WEIGHT,
    SOURCE_WEIGHT,
    RECENCY_WEIGHT,
    SANCTIONS_WEIGHT,
    COUNTRY_RISK_WEIGHT,
)


TOTAL_SOURCES = 3


COUNTRY_RISK_INDEX = {
    "INDIA": 30,
    "USA": 20,
    "UNITED STATES": 20,
    "UK": 20,
    "UNITED KINGDOM": 20,
    "GERMANY": 20,
    "FRANCE": 25,
    "CANADA": 20,
    "AUSTRALIA": 20,
    "JAPAN": 20,
    "RUSSIA": 70,
    "IRAN": 90,
    "NORTH KOREA": 100,
}


def parse_date(
    value: str | None,
) -> date | None:

    if not value:
        return None

    value = str(value).strip()

    if not value:
        return None

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(
                value,
                fmt,
            ).date()
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        ).date()
    except ValueError:
        return None


def calculate_recency_score(
    listed_date: str | None,
) -> float:

    parsed_date = parse_date(listed_date)

    if parsed_date is None:
        return 50.0

    today = date.today()

    age_days = (today - parsed_date).days

    if age_days < 0:
        age_days = 0

    if age_days <= 30:
        return 100.0

    if age_days <= 90:
        return 90.0

    if age_days <= 180:
        return 75.0

    if age_days <= 365:
        return 60.0

    if age_days <= 730:
        return 40.0

    return 20.0


def calculate_risk_score(
    match_score: int | float,
    matched_sources: list[str],
    listed_date: str | None,
) -> dict:

    confidence_score = max(
        0.0,
        min(
            float(match_score),
            100.0,
        ),
    )

    unique_sources = {
        source.strip().upper()
        for source in (
            matched_sources or []
        )
        if source
        and source.strip()
    }

    source_score = (
        len(unique_sources)
        / TOTAL_SOURCES
    ) * 100

    source_score = max(
        0.0,
        min(
            source_score,
            100.0,
        ),
    )

    recency_score = calculate_recency_score(
        listed_date
    )

    # Config-driven weighted risk calculation
    weighted_score = (
        confidence_score
        * CONFIDENCE_WEIGHT
        + source_score
        * SOURCE_WEIGHT
        + recency_score
        * RECENCY_WEIGHT
    )

    bounded_score = max(
        0.0,
        min(
            weighted_score,
            100.0,
        ),
    )

    risk_score = int(
        round(
            bounded_score
        )
    )

    return {
        "risk_score": risk_score,
        "risk_factors": {
            "match_confidence": round(
                confidence_score,
                2,
            ),
            "source_coverage": round(
                source_score,
                2,
            ),
            "recency": round(
                recency_score,
                2,
            ),
        },
    }


def calculate_country_risk(
    country: str | None,
) -> float:

    if not country:
        return 50.0

    normalized_country = (
        country.strip().upper()
    )

    if not normalized_country:
        return 50.0

    score = COUNTRY_RISK_INDEX.get(
        normalized_country,
        50.0,
    )

    return float(
        max(
            0.0,
            min(
                float(score),
                100.0,
            ),
        )
    )


def calculate_overall_supplier_risk(
    sanctions_score: float,
    country_risk_score: float,
) -> float:

    sanctions_score = max(
        0.0,
        min(
            float(sanctions_score),
            100.0,
        ),
    )

    country_risk_score = max(
        0.0,
        min(
            float(country_risk_score),
            100.0,
        ),
    )

    # Config-driven overall supplier risk calculation
    overall_score = (
        sanctions_score
        * SANCTIONS_WEIGHT
        + country_risk_score
        * COUNTRY_RISK_WEIGHT
    )

    return round(
        max(
            0.0,
            min(
                overall_score,
                100.0,
            ),
        ),
        2,
    )