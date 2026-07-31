from fastapi.testclient import TestClient

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

    assert body["model_version"] == "1.0.0"


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

        assert isinstance(reason["contribution"], (int, float))

    assert returned_features == expected_features


def test_contributions_sum_to_one():
    response = client.post("/detect", json=VALID_REQUEST)

    reasons = response.json()["reasons"]

    total = sum(r["contribution"] for r in reasons)

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