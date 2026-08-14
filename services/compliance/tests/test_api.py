import time

from fastapi.testclient import TestClient

from app.main import app



client = TestClient(app)



def test_screen_api():

    response = client.post(
        "/api/v1/compliance/screen",
        json={
            "entity_name": "HAMAS",
            "entity_type": "supplier",
            "country": "India",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["entity_name"] == "HAMAS"
    assert data["entity_type"] == "supplier"
    assert data["country"] == "India"

    assert data["is_flagged"] is True
    assert data["matched_name"] == "HAMAS"
    assert data["match_score"] == 100

    assert isinstance(
        data["matched_lists"],
        list,
    )

    assert len(
        data["matched_lists"]
    ) >= 1




def test_unknown_entity():

    response = client.post(
        "/api/v1/compliance/screen",
        json={
            "entity_name": "OpenAI",
            "entity_type": "supplier",
            "country": "India",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["entity_name"] == "OpenAI"

    assert data["is_flagged"] is False
    assert data["matched_name"] is None
    assert data["match_score"] == 0
    assert data["matched_lists"] == []



def test_bulk_screen_api():

    response = client.post(
        "/api/v1/compliance/screen-bulk",
        json={
            "entity_names": [
                "HAMAS",
                "OpenAI",
            ],
            "entity_type": "supplier",
            "country": "India",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["entity_type"] == "supplier"
    assert data["country"] == "India"

    assert data["count"] == 2
    assert len(data["results"]) == 2

    hamas = data["results"][0]
    openai = data["results"][1]

    assert hamas["entity_name"] == "HAMAS"
    assert hamas["is_flagged"] is True
    assert hamas["match_score"] == 100

    assert openai["entity_name"] == "OpenAI"
    assert openai["is_flagged"] is False
    assert openai["match_score"] == 0




def test_bulk_preserves_input_order():

    response = client.post(
        "/api/v1/compliance/screen-bulk",
        json={
            "entity_names": [
                "OpenAI",
                "HAMAS",
            ],
            "entity_type": "supplier",
            "country": "India",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 2

    first = data["results"][0]
    second = data["results"][1]

    # OpenAI must remain at position 0
    assert first["entity_name"] == "OpenAI"
    assert first["is_flagged"] is False

    # HAMAS must remain at position 1
    assert second["entity_name"] == "HAMAS"
    assert second["is_flagged"] is True
    assert second["matched_name"] == "HAMAS"



def test_empty_entity_name():

    response = client.post(
        "/api/v1/compliance/screen",
        json={
            "entity_name": "",
            "entity_type": "supplier",
            "country": "India",
        },
    )

    assert response.status_code == 422



def test_screen_under_100ms():

    start = time.perf_counter()

    response = client.post(
        "/api/v1/compliance/screen",
        json={
            "entity_name": "HAMAS",
            "entity_type": "supplier",
            "country": "India",
        },
    )

    elapsed = (
        time.perf_counter()
        - start
    ) * 1000

    assert response.status_code == 200

    assert elapsed < 100, (
        f"Single screen took "
        f"{elapsed:.2f}ms"
    )



def test_bulk_50_names_under_100ms():

    names = [
        f"Definitely Not Sanctioned Company {i}"
        for i in range(50)
    ]

    start = time.perf_counter()

    response = client.post(
        "/api/v1/compliance/screen-bulk",
        json={
            "entity_names": names,
            "entity_type": "supplier",
            "country": "India",
        },
    )

    elapsed = (
        time.perf_counter()
        - start
    ) * 1000

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 50
    assert len(data["results"]) == 50

    assert elapsed < 100, (
        f"50-name bulk took "
        f"{elapsed:.2f}ms"
    )