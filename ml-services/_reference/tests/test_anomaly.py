"""Tests for the Anomaly Detection model adapter."""

import pytest

from src.adapters.anomaly import AnomalyAdapter


def test_anomaly_adapter_metadata():
    adapter = AnomalyAdapter()

    metadata = adapter.metadata()

    assert metadata["model"] == "anomaly"
    assert metadata["model_version"] == "v1"
    assert metadata["status"] == "ready"


def test_anomaly_normal_reading():
    adapter = AnomalyAdapter()

    payload = {
        "temperature": 25,
        "humidity": 50,
        "stock_count": 100,
    }

    result = adapter.predict(payload)

    assert result["is_anomaly"] is False
    assert result["score"] == 0.12
    assert result["label"] == "normal"
    assert result["model_type"] == "stub"


def test_anomaly_detects_high_temperature():
    adapter = AnomalyAdapter()

    payload = {
        "temperature": 90,
        "humidity": 50,
        "stock_count": 100,
    }

    result = adapter.predict(payload)

    assert result["is_anomaly"] is True
    assert result["score"] == 0.85
    assert result["label"] == "anomaly"
    assert result["model_type"] == "stub"


def test_anomaly_detects_low_stock():
    adapter = AnomalyAdapter()

    payload = {
        "temperature": 25,
        "humidity": 50,
        "stock_count": 2,
    }

    result = adapter.predict(payload)

    assert result["is_anomaly"] is True
    assert result["score"] == 0.85
    assert result["label"] == "anomaly"


def test_anomaly_requires_all_features():
    adapter = AnomalyAdapter()

    with pytest.raises(ValueError):
        adapter.predict(
            {
                "temperature": 25,
                "humidity": 50,
            }
        )