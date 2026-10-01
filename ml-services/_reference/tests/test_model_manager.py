from src.model_manager import ModelManager

from src.adapters import (
    ForecastAdapter,
    ETAAdapter,
    AnomalyAdapter,
    RiskAdapter,
)


def create_manager():

    manager = ModelManager()

    manager.register(
        ForecastAdapter()
    )

    manager.register(
        ETAAdapter()
    )

    manager.register(
        AnomalyAdapter()
    )

    manager.register(
        RiskAdapter()
    )

    return manager


def test_all_models_registered():

    manager = create_manager()

    models = manager.list_models()

    names = {
        model["model"]
        for model in models
    }

    assert names == {
        "forecast",
        "eta",
        "anomaly",
        "risk",
    }


def test_eta_prediction():

    manager = create_manager()

    result = manager.predict(
        "eta",
        {
            "origin": "sao paulo",
            "destination": "rio de janeiro",
            "carrier": "carrier-a",
            "weight_kg": 2.5,
        },
    )

    assert result["model"] == "eta"
    assert result["model_version"] == "v1"
    assert "prediction" in result
    assert "latency_ms" in result


def test_anomaly_prediction():

    manager = create_manager()

    result = manager.predict(
        "anomaly",
        {
            "temperature": 25.0,
            "humidity": 50.0,
            "stock_count": 100,
        },
    )

    assert result["model"] == "anomaly"
    assert result["model_version"] == "v1"


def test_risk_prediction():

    manager = create_manager()

    result = manager.predict(
        "risk",
        {
            "supplier_name": "ABC Supplier",
            "headlines": [
                "Supplier delivery is delayed"
            ],
        },
    )

    assert result["model"] == "risk"
    assert result["model_version"] == "v1"


def test_unknown_model():

    manager = create_manager()

    try:

        manager.predict(
            "unknown",
            {},
        )

        assert False

    except KeyError:

        assert True