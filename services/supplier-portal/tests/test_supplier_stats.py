from datetime import date

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.main import app
from app.services.purchase_order_service import purchase_orders
from app.services.invoice_service import invoices
from app.schemas.supplier_stats import (
    SupplierStatsResponse,
    SupplierScorecard,
)


client = TestClient(app)


# ============================================================
# TEST SETUP
# ============================================================

def setup_function():
    purchase_orders.clear()
    invoices.clear()


# ============================================================
# SAMPLE DATA
# ============================================================

def create_sample_data():
    purchase_orders["PO1001"] = {
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-07-20T10:00:00",
        "expected_delivery": date(2026, 7, 29),
        "actual_delivery_date": date(2026, 7, 28),
    }

    purchase_orders["PO1002"] = {
        "po_number": "PO1002",
        "supplier_id": "SUP001",
        "status": "acknowledged",
        "created_at": "2026-07-22T10:00:00",
        "expected_delivery": date(2026, 7, 31),
        "actual_delivery_date": None,
    }

    invoices["INV1001"] = {
        "invoice_number": "INV1001",
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "invoice_date": "2026-07-23",
        "dispute": None,
    }


# ============================================================
# SUPPLIER STATS
# ============================================================

def test_supplier_stats():
    """
    Total POs = 2
    On-time POs = 1

    1 / 2 * 100 = 50%
    """

    create_sample_data()

    response = client.get(
        "/api/v1/suppliers/SUP001/stats"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["supplier_id"] == "SUP001"
    assert body["po_count"] == 2
    assert body["on_time_percentage"] == 50.0
    assert body["average_invoice_cycle_time"] == 3.0


def test_supplier_not_found():
    response = client.get(
        "/api/v1/suppliers/SUP999/stats"
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Supplier 'SUP999' not found."
    )


# ============================================================
# STATS - ALL POs ON TIME
# ============================================================

def test_supplier_stats_all_pos_on_time():
    purchase_orders["PO1001"] = {
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-07-20T10:00:00",
        "expected_delivery": date(2026, 7, 29),
        "actual_delivery_date": date(2026, 7, 28),
    }

    purchase_orders["PO1002"] = {
        "po_number": "PO1002",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-07-21T10:00:00",
        "expected_delivery": date(2026, 7, 30),
        "actual_delivery_date": date(2026, 7, 29),
    }

    response = client.get(
        "/api/v1/suppliers/SUP001/stats"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["po_count"] == 2
    assert body["on_time_percentage"] == 100.0


# ============================================================
# STATS - NO PO ON TIME
# ============================================================

def test_supplier_stats_no_po_on_time():
    purchase_orders["PO1001"] = {
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-07-20T10:00:00",
        "expected_delivery": date(2026, 7, 29),
        "actual_delivery_date": date(2026, 7, 31),
    }

    purchase_orders["PO1002"] = {
        "po_number": "PO1002",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-07-21T10:00:00",
        "expected_delivery": date(2026, 7, 30),
        "actual_delivery_date": date(2026, 8, 2),
    }

    response = client.get(
        "/api/v1/suppliers/SUP001/stats"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["po_count"] == 2
    assert body["on_time_percentage"] == 0.0


# ============================================================
# STATS - MIXED ON-TIME / LATE
# ============================================================

def test_supplier_stats_mixed_delivery():
    purchase_orders["PO1001"] = {
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-07-20T10:00:00",
        "expected_delivery": date(2026, 7, 29),
        "actual_delivery_date": date(2026, 7, 29),
    }

    purchase_orders["PO1002"] = {
        "po_number": "PO1002",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-07-21T10:00:00",
        "expected_delivery": date(2026, 7, 30),
        "actual_delivery_date": date(2026, 8, 1),
    }

    purchase_orders["PO1003"] = {
        "po_number": "PO1003",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-07-22T10:00:00",
        "expected_delivery": date(2026, 8, 1),
        "actual_delivery_date": date(2026, 8, 1),
    }

    response = client.get(
        "/api/v1/suppliers/SUP001/stats"
    )

    assert response.status_code == 200

    body = response.json()

    # 2 on-time / 3 total * 100
    assert body["po_count"] == 3
    assert body["on_time_percentage"] == 66.67


# ============================================================
# STATS - UNFULFILLED PO IS STILL IN TOTAL
# ============================================================

def test_supplier_stats_unfulfilled_po_in_total():
    create_sample_data()

    response = client.get(
        "/api/v1/suppliers/SUP001/stats"
    )

    assert response.status_code == 200

    body = response.json()

    # PO1001 = on-time
    # PO1002 = acknowledged
    #
    # Total = 2
    # On-time = 1
    #
    # 1 / 2 * 100 = 50
    assert body["po_count"] == 2
    assert body["on_time_percentage"] == 50.0


# ============================================================
# STATS - DELIVERY ON EXPECTED DATE
# ============================================================

def test_delivery_on_expected_date_is_on_time():
    purchase_orders["PO1001"] = {
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-07-20T10:00:00",
        "expected_delivery": date(2026, 7, 29),
        "actual_delivery_date": date(2026, 7, 29),
    }

    response = client.get(
        "/api/v1/suppliers/SUP001/stats"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["on_time_percentage"] == 100.0


# ============================================================
# STATS - MISSING DELIVERY DATE
# ============================================================

def test_supplier_stats_missing_delivery_date():
    purchase_orders["PO1001"] = {
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-07-20T10:00:00",
        "expected_delivery": date(2026, 7, 29),
        "actual_delivery_date": None,
    }

    response = client.get(
        "/api/v1/suppliers/SUP001/stats"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["po_count"] == 1
    assert body["on_time_percentage"] == 0.0


# ============================================================
# SCORECARD
# ============================================================

def test_supplier_scorecard():
    create_sample_data()

    response = client.get(
        "/api/v1/suppliers/SUP001/scorecard"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["supplier_id"] == "SUP001"

    # 1 on-time / 2 total POs = 50%
    assert (
        body["scorecard"]["on_time_delivery_percentage"]
        == 50.0
    )

    # One invoice and no dispute
    assert (
        body["scorecard"]["dispute_rate_percentage"]
        == 0.0
    )

    assert (
        body["scorecard"]["invoice_accuracy_percentage"]
        == 100.0
    )

    # 50% * 40%
    # + 100% * 40%
    # + 100% * 20%
    #
    # = 20 + 40 + 20
    # = 80
    assert body["scorecard"]["overall_score"] == 80.0


# ============================================================
# SCORECARD DETAILS
# ============================================================

def test_supplier_scorecard_details():
    create_sample_data()

    response = client.get(
        "/api/v1/suppliers/SUP001/scorecard"
    )

    assert response.status_code == 200

    body = response.json()

    po_details = body["details"]["purchase_orders"]

    assert po_details["total"] == 2
    assert po_details["fulfilled"] == 1
    assert po_details["on_time"] == 1
    assert po_details["late"] == 0

    invoice_details = body["details"]["invoices"]

    assert invoice_details["total"] == 1
    assert invoice_details["disputed"] == 0
    assert invoice_details["accurate"] == 1
    assert invoice_details["inaccurate"] == 0


# ============================================================
# SCORECARD - DISPUTED INVOICE
# ============================================================

def test_supplier_scorecard_disputed_invoice():
    create_sample_data()

    invoices["INV1001"]["dispute"] = {
        "reason": "Incorrect price"
    }

    response = client.get(
        "/api/v1/suppliers/SUP001/scorecard"
    )

    assert response.status_code == 200

    body = response.json()

    assert (
        body["scorecard"]["dispute_rate_percentage"]
        == 100.0
    )

    assert (
        body["scorecard"]["invoice_accuracy_percentage"]
        == 0.0
    )

    invoice_details = body["details"]["invoices"]

    assert invoice_details["total"] == 1
    assert invoice_details["disputed"] == 1
    assert invoice_details["accurate"] == 0
    assert invoice_details["inaccurate"] == 1


# ============================================================
# SCORECARD - SUPPLIER NOT FOUND
# ============================================================

def test_supplier_scorecard_supplier_not_found():
    response = client.get(
        "/api/v1/suppliers/SUP999/scorecard"
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Supplier 'SUP999' not found."
    )


# ============================================================
# SCORECARD - SUPPLIER EXISTS THROUGH INVOICE
# ============================================================

def test_scorecard_supplier_exists_through_invoice():
    invoices["INV1001"] = {
        "invoice_number": "INV1001",
        "supplier_id": "SUP001",
        "po_number": "PO9999",
        "invoice_date": "2026-07-23",
        "dispute": None,
    }

    response = client.get(
        "/api/v1/suppliers/SUP001/scorecard"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["supplier_id"] == "SUP001"
    assert body["details"]["invoices"]["total"] == 1


# ============================================================
# SCHEMA - SUPPLIER STATS
# ============================================================

def test_supplier_stats_schema():
    data = {
        "supplier_id": "SUP001",
        "po_count": 2,
        "on_time_percentage": 50.0,
        "average_invoice_cycle_time": 3.0,
    }

    model = SupplierStatsResponse(**data)

    assert model.supplier_id == "SUP001"
    assert model.po_count == 2
    assert model.on_time_percentage == 50.0
    assert model.average_invoice_cycle_time == 3.0


# ============================================================
# SCHEMA - INVALID STATS VALUES
# ============================================================

@pytest.mark.parametrize(
    "field,value",
    [
        ("po_count", -1),
        ("on_time_percentage", -1),
        ("on_time_percentage", 101),
        ("average_invoice_cycle_time", -1),
    ],
)
def test_supplier_stats_schema_validation(
    field,
    value,
):
    data = {
        "supplier_id": "SUP001",
        "po_count": 2,
        "on_time_percentage": 50.0,
        "average_invoice_cycle_time": 3.0,
    }

    data[field] = value

    with pytest.raises(ValidationError):
        SupplierStatsResponse(**data)


# ============================================================
# SCHEMA - SCORECARD RESPONSE
# ============================================================

def test_supplier_scorecard_schema():
    data = {
        "supplier_id": "SUP001",
        "scorecard": {
            "on_time_delivery_percentage": 50.0,
            "dispute_rate_percentage": 0.0,
            "invoice_accuracy_percentage": 100.0,
            "overall_score": 80.0,
        },
        "details": {
            "purchase_orders": {
                "total": 2,
                "fulfilled": 1,
                "on_time": 1,
                "late": 0,
            },
            "invoices": {
                "total": 1,
                "disputed": 0,
                "accurate": 1,
                "inaccurate": 0,
            },
        },
    }

    model = SupplierScorecard(**data)

    assert model.supplier_id == "SUP001"
    assert (
        model.scorecard.on_time_delivery_percentage
        == 50.0
    )
    assert (
        model.scorecard.overall_score
        == 80.0
    )


# ============================================================
# SCHEMA - SCORECARD INVALID PERCENTAGE
# ============================================================

@pytest.mark.parametrize(
    "field,value",
    [
        ("on_time_delivery_percentage", -1),
        ("on_time_delivery_percentage", 101),
        ("dispute_rate_percentage", -1),
        ("dispute_rate_percentage", 101),
        ("invoice_accuracy_percentage", -1),
        ("invoice_accuracy_percentage", 101),
        ("overall_score", -1),
        ("overall_score", 101),
    ],
)
def test_scorecard_schema_percentage_validation(
    field,
    value,
):
    data = {
        "supplier_id": "SUP001",
        "scorecard": {
            "on_time_delivery_percentage": 50.0,
            "dispute_rate_percentage": 0.0,
            "invoice_accuracy_percentage": 100.0,
            "overall_score": 80.0,
        },
        "details": {
            "purchase_orders": {
                "total": 2,
                "fulfilled": 1,
                "on_time": 1,
                "late": 0,
            },
            "invoices": {
                "total": 1,
                "disputed": 0,
                "accurate": 1,
                "inaccurate": 0,
            },
        },
    }

    data["scorecard"][field] = value

    with pytest.raises(ValidationError):
        SupplierScorecard(**data)