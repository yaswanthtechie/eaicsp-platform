from fastapi.testclient import TestClient

from api import app


client = TestClient(app)


def test_build_features_success():
    payload = {
        "data": [
            {
                "date": "2024-01-01",
                "sales": 100,
            },
            {
                "date": "2024-01-02",
                "sales": 120,
            },
            {
                "date": "2024-01-03",
                "sales": 130,
            },
        ],
        "date_col": "date",
        "target_col": "sales",
        "config": {
            "lags": [1],
            "windows": [1],
        },
    }

    response = client.post(
        "/features/build",
        json=payload,
    )

    assert response.status_code == 200

    body = response.json()

    assert "features" in body
    assert len(body["features"]) == 3


def test_build_features_missing_target_returns_bad_request():
    payload = {
        "data": [
            {
                "date": "2024-01-01",
                "sales": 100,
            },
            {
                "date": "2024-01-02",
                "sales": 120,
            },
        ],
        "date_col": "date",
        "target_col": "revenue",
    }

    response = client.post(
        "/features/build",
        json=payload,
    )

    assert response.status_code == 400
    assert "revenue" in response.json()["detail"]


def test_build_features_invalid_config_returns_bad_request():
    payload = {
        "data": [
            {
                "date": "2024-01-01",
                "sales": 100,
            },
            {
                "date": "2024-01-02",
                "sales": 120,
            },
        ],
        "date_col": "date",
        "target_col": "sales",
        "config": {
            "lags": [-1],
            "windows": [1],
        },
    }

    response = client.post(
        "/features/build",
        json=payload,
    )

    assert response.status_code == 400


def test_build_features_missing_required_request_field():
    payload = {
        "data": [
            {
                "date": "2024-01-01",
                "sales": 100,
            }
        ],
        "target_col": "sales",
    }

    response = client.post(
        "/features/build",
        json=payload,
    )

    assert response.status_code == 422