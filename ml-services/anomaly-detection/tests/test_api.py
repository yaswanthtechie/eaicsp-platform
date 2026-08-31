from fastapi.testclient import TestClient

from app import app
from src.adaptive_engine_manager import (
    adaptive_engine_manager,
)
from src.model_loader import get_model_version


client = TestClient(app)


# ============================================================
# COMMON REQUESTS
# ============================================================

VALID_REQUEST = {
    "model": "lof",
    "reading": {
        "reading_id": 1,
        "temperature": 22.0,
        "humidity": 45.0,
        "stock_count": 100,
    },
}


VALID_WINDOW_REQUEST = {
    "model": "lof",
    "readings": [
        {
            "reading_id": 1,
            "temperature": 22.0,
            "humidity": 45.0,
            "stock_count": 100,
        },
        {
            "reading_id": 2,
            "temperature": 23.0,
            "humidity": 46.0,
            "stock_count": 102,
        },
        {
            "reading_id": 3,
            "temperature": 38.0,
            "humidity": 45.0,
            "stock_count": 100,
        },
    ],
}


# ============================================================
# MODEL-SPECIFIC ADAPTIVE CONFIGURATION
# ============================================================

EXPECTED_ADAPTIVE_CONFIG = {
    "iforest": {
        "shift_sigma": 1.50,
        "stability_tolerance": 0.20,
        "adaptive_percentile": 98.0,
    },
    "lof": {
        "shift_sigma": 2.50,
        "stability_tolerance": 0.30,
        "adaptive_percentile": 97.0,
    },
    "ocsvm": {
        "shift_sigma": 2.25,
        "stability_tolerance": 0.20,
        "adaptive_percentile": 97.0,
    },
}


ADAPTIVE_MODELS = (
    "iforest",
    "lof",
    "ocsvm",
)


# ============================================================
# REQUEST HELPER
# ============================================================

def adaptive_request(
    model_name,
    reading_id=1,
    temperature=22.0,
    humidity=45.0,
    stock_count=100,
):
    return {
        "model": model_name,
        "reading": {
            "reading_id": reading_id,
            "temperature": temperature,
            "humidity": humidity,
            "stock_count": stock_count,
        },
    }


# ============================================================
# /detect
# ============================================================

def test_detect_returns_200():
    response = client.post(
        "/detect",
        json=VALID_REQUEST,
    )

    assert response.status_code == 200


def test_detect_response_schema():
    response = client.post(
        "/detect",
        json=VALID_REQUEST,
    )

    body = response.json()

    assert body["model"] == "lof"
    assert body["model_label"] == "Local Outlier Factor"

    assert isinstance(
        body["is_anomaly"],
        bool,
    )

    assert isinstance(
        body["score"],
        (int, float),
    )

    assert isinstance(
        body["reasons"],
        list,
    )

    assert len(
        body["reasons"]
    ) == 3

    assert (
        body["model_version"]
        == get_model_version()
    )


def test_reason_fields():
    response = client.post(
        "/detect",
        json=VALID_REQUEST,
    )

    reasons = response.json()["reasons"]

    expected_features = {
        "temperature",
        "humidity",
        "stock_count",
    }

    returned_features = set()

    for reason in reasons:

        assert "feature" in reason
        assert "contribution" in reason

        returned_features.add(
            reason["feature"]
        )

        assert isinstance(
            reason["contribution"],
            (int, float),
        )

    assert (
        returned_features
        == expected_features
    )


def test_contributions_sum_to_one():
    response = client.post(
        "/detect",
        json=VALID_REQUEST,
    )

    reasons = response.json()["reasons"]

    total = sum(
        reason["contribution"]
        for reason in reasons
    )

    assert abs(
        total - 1.0
    ) < 1e-3


def test_score_is_positive():
    response = client.post(
        "/detect",
        json=VALID_REQUEST,
    )

    score = response.json()["score"]

    assert score >= 0


def test_invalid_model():
    payload = {
        **VALID_REQUEST,
        "model": "abc",
    }

    response = client.post(
        "/detect",
        json=payload,
    )

    assert response.status_code in (
        400,
        422,
    )


def test_missing_field():
    payload = {
        "model": "lof",
        "reading": {
            "reading_id": 1,
            "temperature": 22,
            "humidity": 45,
        },
    }

    response = client.post(
        "/detect",
        json=payload,
    )

    assert response.status_code == 422


# ============================================================
# /detect-window
# ============================================================

def test_detect_window_returns_200():
    response = client.post(
        "/detect-window",
        json=VALID_WINDOW_REQUEST,
    )

    assert response.status_code == 200


def test_detect_window_response_schema():
    response = client.post(
        "/detect-window",
        json=VALID_WINDOW_REQUEST,
    )

    body = response.json()

    assert body["model"] == "lof"

    assert (
        body["model_version"]
        == get_model_version()
    )

    assert (
        body["window_size"]
        == len(
            VALID_WINDOW_REQUEST[
                "readings"
            ]
        )
    )

    assert "total_anomalies" in body
    assert "anomalous_readings" in body

    assert isinstance(
        body["total_anomalies"],
        int,
    )

    assert isinstance(
        body["anomalous_readings"],
        list,
    )


def test_detect_window_anomalous_readings_schema():
    response = client.post(
        "/detect-window",
        json=VALID_WINDOW_REQUEST,
    )

    body = response.json()

    assert (
        body["total_anomalies"]
        == len(
            body["anomalous_readings"]
        )
    )

    for anomaly in (
        body["anomalous_readings"]
    ):

        assert "reading_index" in anomaly
        assert "is_anomaly" in anomaly
        assert "score" in anomaly
        assert "reasons" in anomaly

        assert (
            anomaly["is_anomaly"]
            is True
        )

        assert isinstance(
            anomaly["reading_index"],
            int,
        )

        assert isinstance(
            anomaly["score"],
            (int, float),
        )

        assert isinstance(
            anomaly["reasons"],
            list,
        )


def test_detect_window_invalid_model():
    payload = {
        **VALID_WINDOW_REQUEST,
        "model": "invalid",
    }

    response = client.post(
        "/detect-window",
        json=payload,
    )

    assert response.status_code in (
        400,
        422,
    )


def test_detect_window_missing_readings():
    payload = {
        "model": "lof",
    }

    response = client.post(
        "/detect-window",
        json=payload,
    )

    assert response.status_code == 422


# ============================================================
# /detect-adaptive
# ============================================================

def test_detect_adaptive_returns_200():
    """
    Basic API smoke test for all supported models.
    """

    adaptive_engine_manager.reset()

    for index, model_name in enumerate(
        ADAPTIVE_MODELS,
        start=1,
    ):

        response = client.post(
            "/detect-adaptive",
            json=adaptive_request(
                model_name,
                reading_id=index,
            ),
        )

        assert response.status_code == 200, (
            f"{model_name}: "
            f"{response.status_code} "
            f"{response.text}"
        )


def test_detect_adaptive_response_schema():
    """
    Verify the actual PUBLIC /detect-adaptive response.

    Internal AdaptiveEngine lifecycle fields are deliberately
    not required here. Those are tested by the engine lifecycle
    tests.

    Public API fields:

        model
        model_label
        model_version
        score
        model_prediction
        model_is_anomaly
        reasons
        is_anomaly
        adaptive_threshold
        state
        regime_changed
        regime_confirmed
        temporal_drift
        adapted
        alert
    """

    adaptive_engine_manager.reset()

    for index, model_name in enumerate(
        ADAPTIVE_MODELS,
        start=1,
    ):

        response = client.post(
            "/detect-adaptive",
            json=adaptive_request(
                model_name,
                reading_id=index,
            ),
        )

        assert response.status_code == 200

        body = response.json()

        required_fields = {
            "model",
            "model_label",
            "model_version",
            "score",
            "model_prediction",
            "model_is_anomaly",
            "reasons",
            "is_anomaly",
            "adaptive_threshold",
            "state",
            "regime_changed",
            "regime_confirmed",
            "temporal_drift",
            "adapted",
            "alert",
        }

        missing = (
            required_fields
            - set(body.keys())
        )

        assert not missing, (
            f"{model_name}: "
            f"missing API fields: "
            f"{sorted(missing)}"
        )

        assert (
            body["model"]
            == model_name
        )

        assert isinstance(
            body["model_label"],
            str,
        )

        assert (
            body["model_version"]
            == get_model_version()
        )

        assert isinstance(
            body["score"],
            (int, float),
        )

        assert isinstance(
            body["model_prediction"],
            int,
        )

        assert isinstance(
            body["model_is_anomaly"],
            bool,
        )

        assert isinstance(
            body["reasons"],
            list,
        )

        assert len(
            body["reasons"]
        ) == 3

        assert isinstance(
            body["is_anomaly"],
            bool,
        )

        assert isinstance(
            body["adaptive_threshold"],
            (int, float),
        )

        assert isinstance(
            body["state"],
            str,
        )

        assert isinstance(
            body["regime_changed"],
            bool,
        )

        assert isinstance(
            body["regime_confirmed"],
            bool,
        )

        assert isinstance(
            body["temporal_drift"],
            bool,
        )

        assert isinstance(
            body["adapted"],
            bool,
        )

        assert isinstance(
            body["alert"],
            bool,
        )


def test_detect_adaptive_model_specific_configuration():
    """
    Verify that production manager initialization uses the
    calibrated model-specific configuration.

    IFOREST:
        sigma=1.50
        tolerance=0.20
        percentile=98

    LOF:
        sigma=2.50
        tolerance=0.30
        percentile=97

    OCSVM:
        sigma=2.25
        tolerance=0.20
        percentile=97
    """

    adaptive_engine_manager.reset()

    adaptive_engine_manager.initialize()

    for model_name in ADAPTIVE_MODELS:

        expected = (
            EXPECTED_ADAPTIVE_CONFIG[
                model_name
            ]
        )

        engine = (
            adaptive_engine_manager
            .get_engine(
                model_name
            )
        )

        assert (
            engine.shift_sigma
            == expected[
                "shift_sigma"
            ]
        )

        assert (
            engine.stability_tolerance
            == expected[
                "stability_tolerance"
            ]
        )

        assert (
            engine.adaptive_threshold.percentile
            == expected[
                "adaptive_percentile"
            ]
        )


def test_detect_adaptive_starts_from_calibration_threshold():
    """
    Verify that the API exposes the engine's initial
    model-specific adaptive threshold.
    """

    adaptive_engine_manager.reset()

    adaptive_engine_manager.initialize()

    for index, model_name in enumerate(
        ADAPTIVE_MODELS,
        start=1,
    ):

        engine = (
            adaptive_engine_manager
            .get_engine(
                model_name
            )
        )

        expected_threshold = (
            engine.adaptive_threshold
            .get_threshold()
        )

        assert (
            expected_threshold
            is not None
        )

        response = client.post(
            "/detect-adaptive",
            json=adaptive_request(
                model_name,
                reading_id=1000 + index,
            ),
        )

        assert response.status_code == 200

        body = response.json()

        assert (
            "adaptive_threshold"
            in body
        )

        actual_threshold = float(
            body[
                "adaptive_threshold"
            ]
        )

        assert abs(
            actual_threshold
            - float(
                expected_threshold
            )
        ) < 1e-12


def test_detect_adaptive_invalid_model():
    payload = adaptive_request(
        "invalid",
        reading_id=999,
    )

    response = client.post(
        "/detect-adaptive",
        json=payload,
    )

    assert response.status_code in (
        400,
        422,
    )


def test_detect_adaptive_missing_reading_id():
    payload = {
        "model": "lof",
        "reading": {
            "temperature": 22.0,
            "humidity": 45.0,
            "stock_count": 100,
        },
    }

    response = client.post(
        "/detect-adaptive",
        json=payload,
    )

    assert response.status_code == 422


def test_detect_adaptive_missing_reading():
    payload = {
        "model": "lof",
    }

    response = client.post(
        "/detect-adaptive",
        json=payload,
    )

    assert response.status_code == 422


def test_detect_adaptive_invalid_temperature():
    payload = adaptive_request(
        "lof",
        reading_id=1001,
        temperature="invalid",
    )

    response = client.post(
        "/detect-adaptive",
        json=payload,
    )

    assert response.status_code == 422


# ============================================================
# MODEL STATE IS INDEPENDENT
# ============================================================

def test_adaptive_models_have_independent_state():
    """
    Processing one model must not reuse the internal engine
    state of another model.
    """

    adaptive_engine_manager.reset()

    responses = []

    for index, model_name in enumerate(
        ADAPTIVE_MODELS,
        start=1,
    ):

        response = client.post(
            "/detect-adaptive",
            json=adaptive_request(
                model_name,
                reading_id=5000 + index,
            ),
        )

        assert response.status_code == 200

        body = response.json()

        assert (
            body["model"]
            == model_name
        )

        responses.append(
            body
        )

    assert len(
        responses
    ) == 3

    engines = {
        model_name: (
            adaptive_engine_manager
            .get_engine(
                model_name
            )
        )
        for model_name in ADAPTIVE_MODELS
    }

    assert (
        engines["iforest"]
        is not engines["lof"]
    )

    assert (
        engines["lof"]
        is not engines["ocsvm"]
    )

    assert (
        engines["iforest"]
        is not engines["ocsvm"]
    )


# ============================================================
# API ROUTE AVAILABILITY
# ============================================================

def test_all_anomaly_endpoints_exist():

    routes = {
        route.path
        for route in app.routes
    }

    assert "/detect" in routes
    assert "/detect-window" in routes
    assert "/detect-adaptive" in routes