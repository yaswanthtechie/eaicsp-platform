from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_audit_history():

    client.post(

        "/api/v1/compliance/screen",

        json={

            "entity_name": "HAMAS",

            "entity_type": "supplier",

            "country": "India",

        },

    )

    response = client.get(

        "/api/v1/compliance/audit/HAMAS"

    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)

    assert len(data) >= 1

    assert data[0]["entity_name"] == "HAMAS"