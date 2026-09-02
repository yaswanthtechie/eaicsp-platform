import pytest

import app.services.risk_score_service as risk_service
from app.core.config import (
    CONFIDENCE_WEIGHT,
    SOURCE_WEIGHT,
    RECENCY_WEIGHT,
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
    source_score = (2 / risk_service.TOTAL_SOURCES) * 100

    recency_score = result["risk_factors"]["recency"]

    expected = (
        confidence_score * CONFIDENCE_WEIGHT
        + source_score * SOURCE_WEIGHT
        + recency_score * RECENCY_WEIGHT
    )

    expected = max(0.0, min(expected, 100.0))

    assert result["risk_score"] == round(expected)

def test_risk_score_changes_when_configured_weights_change(monkeypatch):
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

    assert changed_result["risk_score"] != original_result["risk_score"]

def test_risk_score_respects_zero_weight(monkeypatch):
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
        (1 / risk_service.TOTAL_SOURCES)
        * 100
    )

    assert result["risk_score"] == expected

def test_risk_score_respects_custom_weight_combination(monkeypatch):
    monkeypatch.setattr(
        risk_service,
        "CONFIDENCE_WEIGHT",
        0.20,
    )
    monkeypatch.setattr(
        risk_service,
        "SOURCE_WEIGHT",
        0.50,
    )
    monkeypatch.setattr(
        risk_service,
        "RECENCY_WEIGHT",
        0.30,
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
        80 * 0.20
        + source_score * 0.50
        + 50 * 0.30
    )

    assert result["risk_score"] == expected