from fastapi.testclient import TestClient

from src.service import app


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

def test_build_features_rejects_non_numeric_target():
    response = client.post(
        "/features/build",
        json={
            "data": [
                {"date": "2024-01-01", "sales": "100"},
                {"date": "2024-01-02", "sales": "abc"},
            ],
            "date_col": "date",
            "target_col": "sales",
            "config": {"lags": [1], "windows": [1]},
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Target column 'sales' must contain numeric values."
    )
def test_build_features_reuses_feature_store_cache(monkeypatch):
    import src.service as service
    import src.feature_store as feature_store

    service.feature_store.clear()

    call_count = {"count": 0}

    original_build_all_features = feature_store.build_all_features

    def tracked_build_all_features(*args, **kwargs):
        call_count["count"] += 1
        return original_build_all_features(*args, **kwargs)

    monkeypatch.setattr(
        feature_store,
        "build_all_features",
        tracked_build_all_features,
    )

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
        "feature_version": "v1",
    }

    first_response = client.post(
        "/features/build",
        json=payload,
    )

    second_response = client.post(
        "/features/build",
        json=payload,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json() == second_response.json()
    assert call_count["count"] == 1

def test_build_features_rejects_more_than_maximum_rows():
    payload = {
        "data": [
            {
                "date": "2024-01-01",
                "sales": 100,
            }
        ]
        * 100_001,
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

    assert response.status_code == 422


def test_build_features_rejects_excessive_lag():
    payload = {
        "data": [
            {
                "date": "2024-01-01",
                "sales": 100,
            }
        ],
        "date_col": "date",
        "target_col": "sales",
        "config": {
            "lags": [366],
            "windows": [1],
        },
    }

    response = client.post(
        "/features/build",
        json=payload,
    )

    assert response.status_code == 400
    assert "exceeds the maximum allowed value" in response.json()["detail"]


def test_build_features_rejects_excessive_window():
    payload = {
        "data": [
            {
                "date": "2024-01-01",
                "sales": 100,
            }
        ],
        "date_col": "date",
        "target_col": "sales",
        "config": {
            "lags": [1],
            "windows": [366],
        },
    }

    response = client.post(
        "/features/build",
        json=payload,
    )

    assert response.status_code == 400
    assert "exceeds the maximum allowed value" in response.json()["detail"]


def test_build_features_accepts_valid_lag_and_window_limits():
    payload = {
        "data": [
            {
                "date": "2024-01-01",
                "sales": 100,
            }
        ],
        "date_col": "date",
        "target_col": "sales",
        "config": {
            "lags": [365],
            "windows": [365],
        },
    }

    response = client.post(
        "/features/build",
        json=payload,
    )

    assert response.status_code == 200
    assert "features" in response.json()

def test_build_features_separates_multiple_series_by_group():
    payload = {
        "data": [
            {"date": "2024-01-01", "sku": "A", "sales": 100},
            {"date": "2024-01-01", "sku": "B", "sales": 5},
            {"date": "2024-01-02", "sku": "A", "sales": 101},
            {"date": "2024-01-02", "sku": "B", "sales": 6},
        ],
        "date_col": "date",
        "target_col": "sales",
        "group_cols": ["sku"],
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

    features = response.json()["features"]

    by_sku = {
        row["sku"]: row
        for row in features
        if row["date"] == "2024-01-02T00:00:00"
    }

    assert by_sku["A"]["sales_lag_1"] == 100
    assert by_sku["B"]["sales_lag_1"] == 5