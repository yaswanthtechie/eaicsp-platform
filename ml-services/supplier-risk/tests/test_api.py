from fastapi.testclient import TestClient
import pytest
from src.analyze import app
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_sentiment_and_model():
    with patch("src.predict.analyze_sentiment") as mock_sentiment, \
         patch("src.analyze.init_model") as mock_init:
        def side_effect(text):
            return {"label": "neutral", "confidence": 0.99}
        mock_sentiment.side_effect = side_effect
        yield mock_sentiment, mock_init


def test_analyze_endpoint_valid_request():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/supplier-risk/analyze",
            json={
                "supplier_name": "TestSupplier",
                "headlines": [
                    "TestSupplier announces a strike and faces a lawsuit.",
                    "TestSupplier reports positive earnings."
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "supplier_summary" in data
        summary = data["supplier_summary"]["TestSupplier"]
        assert summary["supplier"] == "TestSupplier"
        assert "risk_score" in summary
        assert "confidence" in summary
        assert "signals" in summary
        assert "top_worst_3" in summary


def test_predict_endpoint_valid_request():
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json={
                "supplier_name": "AcmeCorp",
                "headlines": [
                    "AcmeCorp files for bankruptcy amidst debt default.",
                    "AcmeCorp secures new restructuring plan."
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "AcmeCorp" in data["supplier_summary"]


def test_analyze_endpoint_blank_supplier_name():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/supplier-risk/analyze",
            json={
                "supplier_name": "   ",
                "headlines": ["Some headline."]
            }
        )
        assert response.status_code == 422


def test_analyze_endpoint_empty_supplier_name():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/supplier-risk/analyze",
            json={
                "supplier_name": "",
                "headlines": ["Some headline."]
            }
        )
        assert response.status_code == 422


def test_analyze_endpoint_supplier_name_too_long():
    with TestClient(app) as client:
        long_name = "A" * 201
        response = client.post(
            "/predict",
            json={
                "supplier_name": long_name,
                "headlines": ["Some headline."]
            }
        )
        assert response.status_code == 422


def test_analyze_endpoint_too_many_headlines():
    with TestClient(app) as client:
        headlines = [f"Headline {i}" for i in range(51)]
        response = client.post(
            "/predict",
            json={
                "supplier_name": "TestSupplier",
                "headlines": headlines
            }
        )
        assert response.status_code == 422


def test_oversized_400_request_does_not_trigger_inference(mock_sentiment_and_model):
    mock_sentiment, _ = mock_sentiment_and_model
    with TestClient(app) as client:
        headlines = [f"Headline {i}" for i in range(400)]
        response = client.post(
            "/predict",
            json={
                "supplier_name": "LargeBatchSupplier",
                "headlines": headlines
            }
        )
        assert response.status_code == 422
        # Confirm transformer inference was never invoked
        assert mock_sentiment.call_count == 0


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "UP", "service": "supplier-risk"}
