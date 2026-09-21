
import pytest

import app.services.risk_score_service as risk_service
from app.core.config import (
    CONFIDENCE_WEIGHT,
    SOURCE_WEIGHT,
    RECENCY_WEIGHT,
    SANCTIONS_WEIGHT,
    COUNTRY_RISK_WEIGHT,
    COUNTRY_RISK_INDEX,
    UNKNOWN_COUNTRY_RISK,
)


def test_risk_weights_sum_to_one():
    total = (
        CONFIDENCE_WEIGHT
        + SOURCE_WEIGHT
        + RECENCY_WEIGHT
    )

    assert total == pytest.approx(1.0)


def test_risk_score_uses_configured_weights():
    match_score = 80
    matched_sources = ["OFAC", "UN"]
    listed_date = None

    result = risk_service.calculate_risk_score(
        match_score=match_score,
        matched_sources=matched_sources,
        listed_date=listed_date,
    )

    confidence_score = 80.0
    source_score = (
        2 / risk_service.TOTAL_SOURCES
    ) * 100

    recency_score = result["risk_factors"]["recency"]

    expected = (
        confidence_score * CONFIDENCE_WEIGHT
        + source_score * SOURCE_WEIGHT
        + recency_score * RECENCY_WEIGHT
    )

    expected = max(
        0.0,
        min(
            expected,
            100.0,
        ),
    )

    assert result["risk_score"] == round(expected)


def test_risk_score_changes_when_configured_weights_change(
    monkeypatch,
):
    original_result = risk_service.calculate_risk_score(
        match_score=80,
        matched_sources=["OFAC", "UN"],
        listed_date=None,
    )

    monkeypatch.setattr(
        risk_service,
        "CONFIDENCE_WEIGHT",
        0.70,
    )

    monkeypatch.setattr(
        risk_service,
        "SOURCE_WEIGHT",
        0.20,
    )

    monkeypatch.setattr(
        risk_service,
        "RECENCY_WEIGHT",
        0.10,
    )

    changed_result = risk_service.calculate_risk_score(
        match_score=80,
        matched_sources=["OFAC", "UN"],
        listed_date=None,
    )

    assert changed_result["risk_score"] != (
        original_result["risk_score"]
    )


def test_risk_score_respects_zero_weight(
    monkeypatch,
):
    monkeypatch.setattr(
        risk_service,
        "CONFIDENCE_WEIGHT",
        0.0,
    )

    monkeypatch.setattr(
        risk_service,
        "SOURCE_WEIGHT",
        1.0,
    )

    monkeypatch.setattr(
        risk_service,
        "RECENCY_WEIGHT",
        0.0,
    )

    result = risk_service.calculate_risk_score(
        match_score=100,
        matched_sources=["OFAC"],
        listed_date=None,
    )

    expected = round(
        (
            1
            / risk_service.TOTAL_SOURCES
        )
        * 100
    )

    assert result["risk_score"] == expected


def test_risk_score_respects_custom_weight_combination(
    monkeypatch,
):
    confidence_weight = 0.20
    source_weight = 0.50
    recency_weight = 0.30

    monkeypatch.setattr(
        risk_service,
        "CONFIDENCE_WEIGHT",
        confidence_weight,
    )

    monkeypatch.setattr(
        risk_service,
        "SOURCE_WEIGHT",
        source_weight,
    )

    monkeypatch.setattr(
        risk_service,
        "RECENCY_WEIGHT",
        recency_weight,
    )

    result = risk_service.calculate_risk_score(
        match_score=80,
        matched_sources=["OFAC", "UN"],
        listed_date=None,
    )

    source_score = (
        2 / risk_service.TOTAL_SOURCES
    ) * 100

    expected = round(
        80 * confidence_weight
        + source_score * source_weight
        + 50 * recency_weight
    )

    assert result["risk_score"] == expected


def test_country_risk_uses_configured_values():
    india_result = risk_service.calculate_country_risk(
        "INDIA"
    )

    iran_result = risk_service.calculate_country_risk(
        "IRAN"
    )

    assert india_result == COUNTRY_RISK_INDEX["INDIA"]
    assert iran_result == COUNTRY_RISK_INDEX["IRAN"]


def test_country_risk_is_case_insensitive():
    assert (
        risk_service.calculate_country_risk(
            "india"
        )
        == COUNTRY_RISK_INDEX["INDIA"]
    )

    assert (
        risk_service.calculate_country_risk(
            " India "
        )
        == COUNTRY_RISK_INDEX["INDIA"]
    )


def test_unknown_country_uses_configured_default():
    result = risk_service.calculate_country_risk(
        "UNKNOWN COUNTRY"
    )

    assert result == UNKNOWN_COUNTRY_RISK


def test_empty_country_uses_configured_default():
    assert (
        risk_service.calculate_country_risk(None)
        == UNKNOWN_COUNTRY_RISK
    )

    assert (
        risk_service.calculate_country_risk("")
        == UNKNOWN_COUNTRY_RISK
    )

    assert (
        risk_service.calculate_country_risk("   ")
        == UNKNOWN_COUNTRY_RISK
    )


def test_overall_supplier_risk_uses_configured_weights():
    sanctions_score = 80.0
    country_risk_score = 60.0

    expected = round(
        sanctions_score * SANCTIONS_WEIGHT
        + country_risk_score * COUNTRY_RISK_WEIGHT,
        2,
    )

    result = risk_service.calculate_overall_supplier_risk(
        sanctions_score=sanctions_score,
        country_risk_score=country_risk_score,
    )

    assert result == expected


def test_overall_supplier_risk_changes_when_weights_change(
    monkeypatch,
):
    original_result = (
        risk_service.calculate_overall_supplier_risk(
            sanctions_score=80.0,
            country_risk_score=60.0,
        )
    )

    monkeypatch.setattr(
        risk_service,
        "SANCTIONS_WEIGHT",
        0.60,
    )

    monkeypatch.setattr(
        risk_service,
        "COUNTRY_RISK_WEIGHT",
        0.40,
    )

    changed_result = (
        risk_service.calculate_overall_supplier_risk(
            sanctions_score=80.0,
            country_risk_score=60.0,
        )
    )

    assert changed_result != original_result


def test_overall_supplier_risk_respects_zero_weight(
    monkeypatch,
):
    monkeypatch.setattr(
        risk_service,
        "SANCTIONS_WEIGHT",
        1.0,
    )

    monkeypatch.setattr(
        risk_service,
        "COUNTRY_RISK_WEIGHT",
        0.0,
    )

    result = (
        risk_service.calculate_overall_supplier_risk(
            sanctions_score=80.0,
            country_risk_score=100.0,
        )
    )

    assert result == 80.0


def test_overall_supplier_risk_is_bounded():
    low_result = (
        risk_service.calculate_overall_supplier_risk(
            sanctions_score=-10.0,
            country_risk_score=-20.0,
        )
    )

    high_result = (
        risk_service.calculate_overall_supplier_risk(
            sanctions_score=150.0,
            country_risk_score=200.0,
        )
    )

    assert low_result == 0.0
    assert high_result == 100.0

