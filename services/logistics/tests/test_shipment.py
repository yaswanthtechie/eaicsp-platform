from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.services.shipment_service import (
    shipments,
    shipment_events,
    reset_all_circuit_breakers,
)


client = TestClient(app)


# ============================================================
# TEST SETUP
# ============================================================

def setup_function():
    """
    Clear in-memory data before every test.
    """

    shipments.clear()
    shipment_events.clear()
    reset_all_circuit_breakers()


# ============================================================
# CREATE SHIPMENT
# ============================================================

def test_create_shipment():
    response = client.post(
        "/api/v1/shipments/",
        json={
            "shipment_id": 1,
            "origin": "Hyderabad",
            "destination": "Mumbai",
            "carrier": "dhl",
            "status": "pending",
            "estimated_delivery": "2026-08-20",
            "weight_kg": 10,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["shipment_id"] == 1
    assert data["origin"] == "Hyderabad"
    assert data["destination"] == "Mumbai"
    assert data["carrier"] == "dhl"
    assert data["status"] == "pending"


# ============================================================
# DUPLICATE SHIPMENT
# ============================================================

def test_duplicate_shipment():
    payload = {
        "shipment_id": 2,
        "origin": "Hyderabad",
        "destination": "Delhi",
        "carrier": "ups",
        "status": "pending",
        "estimated_delivery": "2026-08-20",
        "weight_kg": 5,
    }

    first_response = client.post(
        "/api/v1/shipments/",
        json=payload,
    )

    assert first_response.status_code == 200

    second_response = client.post(
        "/api/v1/shipments/",
        json=payload,
    )

    assert second_response.status_code == 409


# ============================================================
# GET ALL SHIPMENTS
# ============================================================

def test_get_all_shipments():
    client.post(
        "/api/v1/shipments/",
        json={
            "shipment_id": 3,
            "origin": "Hyderabad",
            "destination": "Chennai",
            "carrier": "bluedart",
            "status": "pending",
            "estimated_delivery": "2026-08-20",
            "weight_kg": 8,
        },
    )

    response = client.get(
        "/api/v1/shipments/"
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["shipment_id"] == 3


# ============================================================
# GET SHIPMENT BY ID
# ============================================================

def test_get_shipment_by_id():
    client.post(
        "/api/v1/shipments/",
        json={
            "shipment_id": 4,
            "origin": "Hyderabad",
            "destination": "Bangalore",
            "carrier": "dhl",
            "status": "pending",
            "estimated_delivery": "2026-08-20",
            "weight_kg": 12,
        },
    )

    response = client.get(
        "/api/v1/shipments/4"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["shipment_id"] == 4


# ============================================================
# SHIPMENT NOT FOUND
# ============================================================

def test_shipment_not_found():
    response = client.get(
        "/api/v1/shipments/9999"
    )

    assert response.status_code == 404


# ============================================================
# UPDATE SHIPMENT
# ============================================================

def test_update_shipment_status():
    client.post(
        "/api/v1/shipments/",
        json={
            "shipment_id": 5,
            "origin": "Hyderabad",
            "destination": "Mumbai",
            "carrier": "ups",
            "status": "pending",
            "estimated_delivery": "2026-08-20",
            "weight_kg": 15,
        },
    )

    response = client.put(
        "/api/v1/shipments/5",
        json={
            "shipment_id": 5,
            "origin": "Hyderabad",
            "destination": "Mumbai",
            "carrier": "ups",
            "status": "in_transit",
            "estimated_delivery": "2026-08-20",
            "weight_kg": 15,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "in_transit"


# ============================================================
# INVALID STATUS TRANSITION
# ============================================================

def test_invalid_status_transition():
    client.post(
        "/api/v1/shipments/",
        json={
            "shipment_id": 6,
            "origin": "Hyderabad",
            "destination": "Delhi",
            "carrier": "dhl",
            "status": "pending",
            "estimated_delivery": "2026-08-20",
            "weight_kg": 10,
        },
    )

    response = client.put(
        "/api/v1/shipments/6",
        json={
            "shipment_id": 6,
            "origin": "Hyderabad",
            "destination": "Delhi",
            "carrier": "dhl",
            "status": "delivered",
            "estimated_delivery": "2026-08-20",
            "weight_kg": 10,
        },
    )

    assert response.status_code == 400


# ============================================================
# FILTER BY STATUS
# ============================================================

def test_filter_shipments_by_status():
    client.post(
        "/api/v1/shipments/",
        json={
            "shipment_id": 7,
            "origin": "Hyderabad",
            "destination": "Mumbai",
            "carrier": "fedex",
            "status": "pending",
            "estimated_delivery": "2026-08-20",
            "weight_kg": 10,
        },
    )

    response = client.get(
        "/api/v1/shipments/?status=pending"
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["status"] == "pending"


# ============================================================
# SHIPMENT HISTORY
# ============================================================

def test_shipment_history():
    client.post(
        "/api/v1/shipments/",
        json={
            "shipment_id": 8,
            "origin": "Hyderabad",
            "destination": "Chennai",
            "carrier": "bluedart",
            "status": "pending",
            "estimated_delivery": "2026-08-20",
            "weight_kg": 7,
        },
    )

    client.put(
        "/api/v1/shipments/8",
        json={
            "shipment_id": 8,
            "origin": "Hyderabad",
            "destination": "Chennai",
            "carrier": "bluedart",
            "status": "in_transit",
            "estimated_delivery": "2026-08-20",
            "weight_kg": 7,
        },
    )

    response = client.get(
        "/api/v1/shipments/8/history"
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["status"] == "pending"
    assert data[1]["status"] == "in_transit"


# ============================================================
# SINGLE QUOTE
# ============================================================

def test_single_quote():
    response = client.post(
        "/api/v1/shipments/quote",
        json={
            "origin": "Hyderabad",
            "destination": "Mumbai",
            "weight_kg": 10,
            "preference": "cheapest",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "rates" in data
    assert "warnings" in data


# ============================================================
# BULK QUOTE
# ============================================================

def test_bulk_quote():
    response = client.post(
        "/api/v1/shipments/bulk-quote",
        json={
            "shipments": [
                {
                    "origin": "Hyderabad",
                    "destination": "Mumbai",
                    "weight_kg": 10,
                    "preference": "cheapest",
                },
                {
                    "origin": "Hyderabad",
                    "destination": "Delhi",
                    "weight_kg": 5,
                    "preference": "fastest",
                },
            ]
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "quotes" in data
    assert "performance" in data

    assert len(data["quotes"]) == 2

    performance = data["performance"]

    assert performance["shipment_count"] == 2
    assert performance["parallel_seconds"] >= 0


# ============================================================
# BULK QUOTE BENCHMARK
# ============================================================

def test_bulk_quote_benchmark():
    response = client.post(
        "/api/v1/shipments/bulk-quote?benchmark=true",
        json={
            "shipments": [
                {
                    "origin": "Hyderabad",
                    "destination": "Mumbai",
                    "weight_kg": 10,
                    "preference": "cheapest",
                },
                {
                    "origin": "Hyderabad",
                    "destination": "Delhi",
                    "weight_kg": 10,
                    "preference": "fastest",
                },
            ]
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "quotes" in data
    assert "performance" in data

    performance = data["performance"]

    assert performance["shipment_count"] == 2
    assert performance["parallel_seconds"] >= 0
    assert performance["sequential_seconds"] is not None
    assert performance["speedup"] is not None


# ============================================================
# BULK QUOTE MAXIMUM 20
# ============================================================

def test_bulk_quote_maximum_20():
    requests = []

    for _ in range(20):
        requests.append(
            {
                "origin": "Hyderabad",
                "destination": "Mumbai",
                "weight_kg": 5,
                "preference": "cheapest",
            }
        )

    response = client.post(
        "/api/v1/shipments/bulk-quote",
        json={
            "shipments": requests
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["quotes"]) == 20


# ============================================================
# BULK QUOTE MORE THAN 20
# ============================================================

def test_bulk_quote_more_than_20():
    requests = []

    for _ in range(21):
        requests.append(
            {
                "origin": "Hyderabad",
                "destination": "Mumbai",
                "weight_kg": 5,
                "preference": "cheapest",
            }
        )

    response = client.post(
        "/api/v1/shipments/bulk-quote",
        json={
            "shipments": requests
        },
    )

    assert response.status_code == 422


# ============================================================
# CIRCUIT BREAKER STATUS
# ============================================================

def test_circuit_breaker_status():
    response = client.get(
        "/api/v1/shipments/circuit-breaker-status"
    )

    assert response.status_code == 200

    data = response.json()

    assert "dhl" in data
    assert "fedex" in data
    assert "ups" in data
    assert "bluedart" in data


# ============================================================
# CONSOLIDATION SUGGESTIONS
# ============================================================

def test_consolidation_suggestions():
    client.post(
        "/api/v1/shipments/",
        json={
            "shipment_id": 20,
            "origin": "Hyderabad",
            "destination": "Mumbai",
            "carrier": "dhl",
            "status": "pending",
            "estimated_delivery": "2026-08-20",
            "weight_kg": 10,
        },
    )

    client.post(
        "/api/v1/shipments/",
        json={
            "shipment_id": 21,
            "origin": "Hyderabad",
            "destination": "Mumbai",
            "carrier": "ups",
            "status": "pending",
            "estimated_delivery": "2026-08-21",
            "weight_kg": 15,
        },
    )

    response = client.get(
        "/api/v1/shipments/consolidation-suggestions"
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) >= 1

    assert 20 in data[0]["shipment_ids"]
    assert 21 in data[0]["shipment_ids"]


# ============================================================
# ETA EXPLANATION
# ============================================================

def test_eta_explanation():
    client.post(
        "/api/v1/shipments/",
        json={
            "shipment_id": 30,
            "origin": "Hyderabad",
            "destination": "Mumbai",
            "carrier": "dhl",
            "status": "pending",
            "estimated_delivery": "2026-08-20",
            "weight_kg": 10,
        },
    )

    response = client.get(
        "/api/v1/shipments/30/eta-explain"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["shipment_id"] == 30
    assert "distance_km" in data
    assert "reliability_score" in data
    assert "estimated_days" in data
    assert "explanation" in data


# ============================================================
# DELETE SHIPMENT
# ============================================================

def test_delete_shipment():
    client.post(
        "/api/v1/shipments/",
        json={
            "shipment_id": 40,
            "origin": "Hyderabad",
            "destination": "Delhi",
            "carrier": "ups",
            "status": "pending",
            "estimated_delivery": "2026-08-20",
            "weight_kg": 10,
        },
    )

    response = client.delete(
        "/api/v1/shipments/40"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == (
        "Shipment deleted successfully"
    )

    get_response = client.get(
        "/api/v1/shipments/40"
    )

    assert get_response.status_code == 404