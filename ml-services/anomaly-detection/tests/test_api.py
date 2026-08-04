from fastapi.testclient import TestClient
from src.model_loader import get_model_version
from app import app

client = TestClient(app)


VALID_REQUEST = {
    "model": "lof",
    "reading": {
        "temperature": 22.0,
        "humidity": 45.0,
        "stock_count": 100,
    },
}

VALID_WINDOW_REQUEST = {
    "model": "lof",
    "readings": [
        {
            "temperature": 22.0,
            "humidity": 45.0,
            "stock_count": 100,
        },
        {
            "temperature": 23.0,
            "humidity": 46.0,
            "stock_count": 102,
        },
        {
            "temperature": 38.0,
            "humidity": 45.0,
            "stock_count": 100,
        },
    ],
}


def test_detect_returns_200():
    response = client.post("/detect", json=VALID_REQUEST)

    assert response.status_code == 200


def test_detect_response_schema():
    response = client.post("/detect", json=VALID_REQUEST)

    body = response.json()

    assert body["model"] == "lof"
    assert body["model_label"] == "Local Outlier Factor"

    assert isinstance(body["is_anomaly"], bool)
    assert isinstance(body["score"], (int, float))

    assert isinstance(body["reasons"], list)
    assert len(body["reasons"]) == 3

    assert body["model_version"] == get_model_version()


def test_reason_fields():
    response = client.post("/detect", json=VALID_REQUEST)

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

        returned_features.add(reason["feature"])

        assert isinstance(
            reason["contribution"],
            (int, float),
        )

    assert returned_features == expected_features


def test_contributions_sum_to_one():
    response = client.post("/detect", json=VALID_REQUEST)

    reasons = response.json()["reasons"]

    total = sum(
        r["contribution"]
        for r in reasons
    )

    assert abs(total - 1.0) < 1e-3


def test_score_is_positive():
    response = client.post("/detect", json=VALID_REQUEST)

    score = response.json()["score"]

    assert score >= 0


def test_invalid_model():
    payload = VALID_REQUEST.copy()
    payload["model"] = "abc"

    response = client.post("/detect", json=payload)

    assert response.status_code in (400, 422)


def test_missing_field():
    payload = {
        "model": "lof",
        "reading": {
            "temperature": 22,
            "humidity": 45,
        },
    }

    response = client.post("/detect", json=payload)

    assert response.status_code == 422


# detect-window endpoint

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
    assert body["model_version"] == get_model_version()

    assert body["window_size"] == len(
        VALID_WINDOW_REQUEST["readings"]
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

    assert body["total_anomalies"] == len(
        body["anomalous_readings"]
    )

    for anomaly in body["anomalous_readings"]:

        assert "reading_index" in anomaly
        assert "is_anomaly" in anomaly
        assert "score" in anomaly
        assert "reasons" in anomaly

        assert anomaly["is_anomaly"] is True

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
    payload = VALID_WINDOW_REQUEST.copy()
    payload["model"] = "invalid"

    response = client.post(
        "/detect-window",
        json=payload,
    )

    assert response.status_code in (400, 422)


def test_detect_window_missing_readings():
    payload = {
        "model": "lof",
    }

    response = client.post(
        "/detect-window",
        json=payload,
    )

    assert response.status_code == 422