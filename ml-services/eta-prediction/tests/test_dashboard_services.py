import pytest
import requests
from dashboard.services import anomaly_service, eta_service


def test_anomaly_service_uses_default_port(monkeypatch):
    monkeypatch.delenv("ANOMALY_SERVICE_URL", raising=False)

    captured = {}

    class FakeResponse:
        ok = True

        def json(self):
            return {"is_anomaly": False}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        anomaly_service.requests,
        "post",
        fake_post,
    )

    result = anomaly_service.detect_anomaly({})

    assert captured["url"] == "http://localhost:8000/detect"
    assert result == {"is_anomaly": False}


def test_anomaly_service_reads_url_at_call_time(monkeypatch):
    captured_urls = []

    class FakeResponse:
        ok = True

        def json(self):
            return {"ok": True}

    def fake_post(url, json, timeout):
        captured_urls.append(url)
        return FakeResponse()

    monkeypatch.setattr(
        anomaly_service.requests,
        "post",
        fake_post,
    )

    monkeypatch.setenv(
        "ANOMALY_SERVICE_URL",
        "http://example.com",
    )

    anomaly_service.detect_anomaly({})

    monkeypatch.setenv(
        "ANOMALY_SERVICE_URL",
        "http://another.example.com/",
    )

    anomaly_service.detect_anomaly({})

    assert captured_urls == [
        "http://example.com/detect",
        "http://another.example.com/detect",
    ]


def test_anomaly_service_preserves_http_error_detail(monkeypatch):
    class FakeResponse:
        ok = False
        status_code = 503
        text = "service unavailable"

        def json(self):
            return {"detail": "model service is down"}

    monkeypatch.setattr(
        anomaly_service.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(anomaly_service.AnomalyServiceError) as exc_info:
        anomaly_service.detect_anomaly({})

    assert (
        "Anomaly service returned 503: model service is down"
        in str(exc_info.value)
    )


def test_anomaly_service_handles_non_json_error(monkeypatch):
    class FakeResponse:
        ok = False
        status_code = 500
        text = "Internal Server Error"

        def json(self):
            raise ValueError("not JSON")

    monkeypatch.setattr(
        anomaly_service.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(anomaly_service.AnomalyServiceError) as exc_info:
        anomaly_service.detect_anomaly({})

    assert (
        "Anomaly service returned 500: Internal Server Error"
        in str(exc_info.value)
    )


def test_anomaly_service_reports_unreachable_service(monkeypatch):
    def fake_post(*args, **kwargs):
        raise anomaly_service.requests.ConnectionError(
            "connection refused"
        )

    monkeypatch.setattr(
        anomaly_service.requests,
        "post",
        fake_post,
    )

    with pytest.raises(anomaly_service.AnomalyServiceError) as exc_info:
        anomaly_service.detect_anomaly({})

    assert "Anomaly service is not reachable" in str(exc_info.value)


def test_eta_dashboard_adapter_propagates_missing_model(monkeypatch):
    def fake_predict(payload):
        raise FileNotFoundError("eta_pipeline.joblib")

    monkeypatch.setattr(
        eta_service,
        "predict",
        fake_predict,
    )

    with pytest.raises(FileNotFoundError, match="eta_pipeline.joblib"):
        eta_service.predict_eta(
            {
                "origin": "sao paulo",
                "destination": "rio de janeiro",
                "carrier": "carrier_1",
                "weight_kg": 2.5,
            }
        )


def test_eta_dashboard_adapter(monkeypatch):
    expected = {
        "eta_days": 20.28,
        "confidence_low": 10.08,
        "confidence_high": 30.48,
    }

    def fake_predict(payload):
        assert payload == {
            "origin": "sao paulo",
            "destination": "rio de janeiro",
            "carrier": "carrier_1",
            "weight_kg": 2.5,
        }
        return expected

    monkeypatch.setattr(
        eta_service,
        "predict",
        fake_predict,
    )

    result = eta_service.predict_eta(
        {
            "origin": "sao paulo",
            "destination": "rio de janeiro",
            "carrier": "carrier_1",
            "weight_kg": 2.5,
        }
    )

    assert result == expected