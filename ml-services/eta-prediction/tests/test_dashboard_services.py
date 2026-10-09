from dashboard.services import anomaly_service, eta_service


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

    monkeypatch.setattr(eta_service, "predict", fake_predict)

    result = eta_service.predict_eta(
        {
            "origin": "sao paulo",
            "destination": "rio de janeiro",
            "carrier": "carrier_1",
            "weight_kg": 2.5,
        }
    )

    assert result == expected


def test_anomaly_dashboard_adapter(monkeypatch):
    expected = {
        "is_anomaly": True,
        "score": 0.05,
        "production_threshold": -0.0482,
        "model_label": "Isolation Forest",
        "model_version": "1.0.0",
        "reasons": [],
    }

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return expected

    def fake_post(url, json, timeout):
        assert url == "http://localhost:8001/detect"
        assert json == {
            "model": "iforest",
            "reading": {
                "reading_id": 1,
                "temperature": 25.0,
                "humidity": 50.0,
                "stock_count": 100,
            },
        }
        assert timeout == 10
        return FakeResponse()

    monkeypatch.setattr(
        anomaly_service.requests,
        "post",
        fake_post,
    )

    result = anomaly_service.detect_anomaly(
        {
            "model": "iforest",
            "reading": {
                "reading_id": 1,
                "temperature": 25.0,
                "humidity": 50.0,
                "stock_count": 100,
            },
        }
    )

    assert result == expected


def test_anomaly_dashboard_adapter_raises_for_http_error(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            raise anomaly_service.requests.HTTPError(
                "503 Service Unavailable"
            )

    monkeypatch.setattr(
        anomaly_service.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(),
    )

    try:
        anomaly_service.detect_anomaly({})
        assert False, "Expected HTTPError"
    except anomaly_service.requests.HTTPError as exc:
        assert "503" in str(exc)


def test_anomaly_service_url_can_be_configured(monkeypatch):
    monkeypatch.setenv(
        "ANOMALY_SERVICE_URL",
        "http://example.com",
    )

    import importlib
    import dashboard.config as config

    importlib.reload(config)

    assert config.ANOMALY_SERVICE_URL == "http://example.com"