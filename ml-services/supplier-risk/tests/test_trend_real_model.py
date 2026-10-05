import json
import re
from pathlib import Path

import pytest

from src.analyze import TrendResponse
from src.data import load_active_trend_headlines
from src.trend import calculate_supplier_trend

pytestmark = pytest.mark.slow

DISTRESSED = [
    "Apex Logistics",
    "Northvolt",
    "Silicon Power Storage",
    "Evergrande Construction Logistics",
]

CLEAN = [
    "Siemens",
    "Texas Instruments",
    "ASML",
    "Lockheed Martin",
    "Schneider Electric",
]


@pytest.fixture(scope="module")
def trends():
    data = load_active_trend_headlines()
    return {name: calculate_supplier_trend(name, recs) for name, recs in data.items()}


def test_apex_peak_is_critical(trends):
    apex = trends["Apex Logistics"]
    assert apex["peak_risk_tier"] == "Critical", apex


def test_distressed_suppliers_never_gate_as_low(trends):
    for name in DISTRESSED:
        assert trends[name]["peak_risk_tier"] in ("High", "Critical"), (
            name,
            trends[name]["peak_risk_score"],
        )


def test_low_to_low_noise_is_not_flagged(trends):
    for name in CLEAN:
        t = trends[name]
        if t["current_risk_tier"] == "Low":
            assert t["is_deteriorating"] is False, (
                name,
                t["deterioration_summary"],
            )


def test_contract_example_matches_real_model():
    content = (
        Path(__file__).resolve().parent.parent
        / "COMPLIANCE_INTEGRATION_CONTRACT.md"
    ).read_text(encoding="utf-8")

    blocks = [
        json.loads(b)
        for b in re.findall(r"```json\s*(\{[\s\S]*?\})\s*```", content)
    ]

    request = next(b for b in blocks if "articles" in b)
    documented = next(b for b in blocks if "current_risk_score" in b)

    TrendResponse(**documented)

    actual = calculate_supplier_trend(
        request["supplier_name"],
        request["articles"],
        as_of_date=request.get("as_of_date"),
    )

    for key in (
        "current_risk_score",
        "previous_risk_score",
        "risk_delta",
        "current_risk_tier",
        "peak_risk_tier",
        "trend_direction",
        "is_deteriorating",
        "article_count",
        "window_start",
        "window_end",
    ):
        expected = documented[key]
        got = actual[key]

        if isinstance(expected, float):
            assert got == pytest.approx(expected, abs=0.5), key
        else:
            assert got == expected, key
