"""Tests for the Supplier Risk model adapter."""

import pytest

from src.adapters.risk import RiskAdapter


def test_risk_adapter_metadata():
    adapter = RiskAdapter()

    metadata = adapter.metadata()

    assert metadata["model"] == "risk"
    assert metadata["model_version"] == "v1"
    assert metadata["status"] == "ready"


def test_risk_prediction():
    adapter = RiskAdapter()

    payload = {
        "supplier_name": "Supplier A",
        "headlines": [
            "Supplier expands operations",
            "New warehouse opened",
        ],
    }

    result = adapter.predict(payload)

    assert result["risk_score"] == 0.25
    assert result["confidence"] == 0.75
    assert result["risk_level"] == "low"
    assert result["supplier"] == "Supplier A"
    assert result["model_type"] == "stub"


def test_risk_requires_supplier_name():
    adapter = RiskAdapter()

    with pytest.raises(ValueError):
        adapter.predict(
            {
                "headlines": ["Supplier news"],
            }
        )


def test_risk_requires_headlines_list():
    adapter = RiskAdapter()

    with pytest.raises(ValueError):
        adapter.predict(
            {
                "supplier_name": "Supplier A",
                "headlines": "Supplier news",
            }
        )