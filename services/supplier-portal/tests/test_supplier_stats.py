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
    """
    Clear in-memory stores before every test.
    """
    purchase_orders.clear()
    invoices.clear()


# ============================================================
# SAMPLE DATA
# ============================================================

def create_sample_data():
    """
    Create a basic supplier dataset.

    PO1001:
        - fulfilled
        - delivered one day early

    PO1002:
        - acknowledged / pending
        - not yet delivered

    INV1001:
        - valid invoice
        - no dispute
        - invoice date is 3 days after PO creation
    """

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
        "status": "approved",
        "dispute": None,
    }


# ============================================================
# SUPPLIER STATS
# ============================================================

def test_supplier_stats():
    """
    Total POs = 2
    Fulfilled POs = 1
    On-time POs = 1

    Current implementation:
        1 / 2 * 100 = 50%

    Invoice cycle:
        2026-07-23 - 2026-07-20 = 3 days
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
    """
    Supplier with neither POs nor invoices
    should return 404.
    """

    response = client.get(
        "/api/v1/suppliers/SUP999/stats"
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Supplier 'SUP999' not found."
    )


def test_supplier_stats_supplier_exists_through_invoice():
    """
    Supplier should be considered valid when the supplier
    has an invoice but no purchase orders.
    """

    invoices["INV1001"] = {
        "invoice_number": "INV1001",
        "supplier_id": "SUP001",
        "po_number": "PO9999",
        "invoice_date": "2026-07-23",
        "dispute": None,
    }

    response = client.get(
        "/api/v1/suppliers/SUP001/stats"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["supplier_id"] == "SUP001"
    assert body["po_count"] == 0
    assert body["on_time_percentage"] == 0.0
    assert body["average_invoice_cycle_time"] == 0.0


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

    assert body["po_count"] == 3

    # 2 on-time / 3 total = 66.67%
    assert body["on_time_percentage"] == 66.67


# ============================================================
# STATS - UNFULFILLED PO INCLUDED IN TOTAL
# ============================================================

def test_supplier_stats_unfulfilled_po_in_total():
    create_sample_data()

    response = client.get(
        "/api/v1/suppliers/SUP001/stats"
    )

    assert response.status_code == 200

    body = response.json()

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
# SCORECARD - BASIC
# ============================================================

def test_supplier_scorecard():
    create_sample_data()

    response = client.get(
        "/api/v1/suppliers/SUP001/scorecard"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["supplier_id"] == "SUP001"

    # --------------------------------------------------------
    # Delivery
    # --------------------------------------------------------

    assert (
        body["scorecard"]["on_time_delivery_percentage"]
        == 50.0
    )

    # --------------------------------------------------------
    # Invoice
    # --------------------------------------------------------

    assert (
        body["scorecard"]["dispute_rate_percentage"]
        == 0.0
    )

    assert (
        body["scorecard"]["invoice_accuracy_percentage"]
        == 100.0
    )

    # --------------------------------------------------------
    # Overall score
    # --------------------------------------------------------

    # 50 * 0.40 = 20
    # 100 * 0.40 = 40
    # 100 * 0.20 = 20
    # Total = 80
    assert body["scorecard"]["overall_score"] == 80.0


# ============================================================
# SCORECARD - RATING AND PERFORMANCE STATUS
# ============================================================

def test_supplier_scorecard_rating_and_status():
    create_sample_data()

    response = client.get(
        "/api/v1/suppliers/SUP001/scorecard"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["scorecard"]["overall_score"] == 80.0

    assert body["scorecard"]["rating"] == "Good"

    assert (
        body["scorecard"]["performance_status"]
        == "Healthy"
    )


# ============================================================
# SCORECARD - SCORE BREAKDOWN
# ============================================================

def test_supplier_scorecard_score_breakdown():
    create_sample_data()

    response = client.get(
        "/api/v1/suppliers/SUP001/scorecard"
    )

    assert response.status_code == 200

    body = response.json()

    breakdown = body["score_breakdown"]

    # --------------------------------------------------------
    # Delivery
    # --------------------------------------------------------

    assert (
        breakdown["on_time_delivery"]["score"]
        == 50.0
    )

    assert (
        breakdown["on_time_delivery"]["weight_percentage"]
        == 40.0
    )

    assert (
        breakdown["on_time_delivery"]["weighted_score"]
        == 20.0
    )

    # --------------------------------------------------------
    # Invoice accuracy
    # --------------------------------------------------------

    assert (
        breakdown["invoice_accuracy"]["score"]
        == 100.0
    )

    assert (
        breakdown["invoice_accuracy"]["weight_percentage"]
        == 40.0
    )

    assert (
        breakdown["invoice_accuracy"]["weighted_score"]
        == 40.0
    )

    # --------------------------------------------------------
    # Dispute performance
    # --------------------------------------------------------

    assert (
        breakdown["dispute_performance"]["score"]
        == 100.0
    )

    assert (
        breakdown["dispute_performance"]["weight_percentage"]
        == 20.0
    )

    assert (
        breakdown["dispute_performance"]["weighted_score"]
        == 20.0
    )


# ============================================================
# SCORECARD - DETAILS
# ============================================================

def test_supplier_scorecard_details():
    create_sample_data()

    response = client.get(
        "/api/v1/suppliers/SUP001/scorecard"
    )

    assert response.status_code == 200

    body = response.json()

    # ========================================================
    # PURCHASE ORDER DETAILS
    # ========================================================

    po_details = body["details"]["purchase_orders"]

    assert po_details["total"] == 2
    assert po_details["fulfilled"] == 1
    assert po_details["on_time"] == 1
    assert po_details["late"] == 0
    assert po_details["pending"] == 1
    assert po_details["cancelled"] == 0

    assert po_details["on_time_percentage"] == 50.0
    assert po_details["late_percentage"] == 0.0
    assert po_details["fulfillment_rate"] == 50.0
    assert po_details["average_delay_days"] == 0.0

    # ========================================================
    # INVOICE DETAILS
    # ========================================================

    invoice_details = body["details"]["invoices"]

    assert invoice_details["total"] == 1
    assert invoice_details["disputed"] == 0
    assert invoice_details["accurate"] == 1
    assert invoice_details["inaccurate"] == 0

    assert invoice_details["approved"] == 1
    assert invoice_details["rejected"] == 0
    assert invoice_details["pending"] == 0

    assert invoice_details["accuracy_percentage"] == 100.0
    assert invoice_details["dispute_rate_percentage"] == 0.0
    assert invoice_details["approval_rate_percentage"] == 100.0

    assert (
        invoice_details["average_cycle_time_days"]
        == 3.0
    )


# ============================================================
# SCORECARD - LATE DELIVERY
# ============================================================

def test_supplier_scorecard_late_delivery():
    purchase_orders["PO1001"] = {
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-07-20T10:00:00",
        "expected_delivery": date(2026, 7, 29),
        "actual_delivery_date": date(2026, 8, 2),
    }

    response = client.get(
        "/api/v1/suppliers/SUP001/scorecard"
    )

    assert response.status_code == 200

    body = response.json()

    po_details = body["details"]["purchase_orders"]

    assert po_details["total"] == 1
    assert po_details["fulfilled"] == 1
    assert po_details["on_time"] == 0
    assert po_details["late"] == 1

    assert po_details["on_time_percentage"] == 0.0
    assert po_details["late_percentage"] == 100.0

    # Aug 2 - Jul 29 = 4 days
    assert po_details["average_delay_days"] == 4.0


# ============================================================
# SCORECARD - MIXED DELIVERY
# ============================================================

def test_supplier_scorecard_mixed_delivery():
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
        "actual_delivery_date": date(2026, 8, 2),
    }

    response = client.get(
        "/api/v1/suppliers/SUP001/scorecard"
    )

    assert response.status_code == 200

    body = response.json()

    po_details = body["details"]["purchase_orders"]

    assert po_details["total"] == 2
    assert po_details["fulfilled"] == 2
    assert po_details["on_time"] == 1
    assert po_details["late"] == 1

    assert po_details["on_time_percentage"] == 50.0
    assert po_details["late_percentage"] == 50.0

    # Only PO1002 is late:
    # Aug 2 - Jul 30 = 3 days
    assert po_details["average_delay_days"] == 3.0


# ============================================================
# SCORECARD - CANCELLED PO
# ============================================================

def test_supplier_scorecard_cancelled_po():
    purchase_orders["PO1001"] = {
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "status": "cancelled",
        "created_at": "2026-07-20T10:00:00",
        "expected_delivery": date(2026, 7, 29),
        "actual_delivery_date": None,
    }

    response = client.get(
        "/api/v1/suppliers/SUP001/scorecard"
    )

    assert response.status_code == 200

    body = response.json()

    po_details = body["details"]["purchase_orders"]

    assert po_details["total"] == 1
    assert po_details["fulfilled"] == 0
    assert po_details["cancelled"] == 1
    assert po_details["pending"] == 0
    assert po_details["on_time"] == 0
    assert po_details["late"] == 0

    assert po_details["fulfillment_rate"] == 0.0


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
# SCORECARD - APPROVED / REJECTED / PENDING INVOICES
# ============================================================

def test_supplier_scorecard_invoice_status_counts():
    create_sample_data()

    invoices["INV1001"]["status"] = "approved"

    invoices["INV1002"] = {
        "invoice_number": "INV1002",
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "invoice_date": "2026-07-24",
        "status": "rejected",
        "dispute": {
            "reason": "Incorrect amount"
        },
    }

    invoices["INV1003"] = {
        "invoice_number": "INV1003",
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "invoice_date": "2026-07-25",
        "status": "submitted",
        "dispute": None,
    }

    response = client.get(
        "/api/v1/suppliers/SUP001/scorecard"
    )

    assert response.status_code == 200

    body = response.json()

    invoice_details = body["details"]["invoices"]

    assert invoice_details["total"] == 3
    assert invoice_details["approved"] == 1
    assert invoice_details["rejected"] == 1
    assert invoice_details["pending"] == 1

    assert invoice_details["disputed"] == 1
    assert invoice_details["accurate"] == 2
    assert invoice_details["inaccurate"] == 1

    assert invoice_details["accuracy_percentage"] == 66.67
    assert invoice_details["dispute_rate_percentage"] == 33.33
    assert invoice_details["approval_rate_percentage"] == 33.33


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
        "status": "submitted",
        "dispute": None,
    }

    response = client.get(
        "/api/v1/suppliers/SUP001/scorecard"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["supplier_id"] == "SUP001"

    assert (
        body["details"]["purchase_orders"]["total"]
        == 0
    )

    assert (
        body["details"]["invoices"]["total"]
        == 1
    )

    assert (
        body["details"]["invoices"]["accurate"]
        == 1
    )


# ============================================================
# SCORECARD - AVERAGE INVOICE CYCLE TIME
# ============================================================

def test_supplier_scorecard_average_invoice_cycle_time():
    create_sample_data()

    invoices["INV1002"] = {
        "invoice_number": "INV1002",
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "invoice_date": "2026-07-25",
        "status": "approved",
        "dispute": None,
    }

    response = client.get(
        "/api/v1/suppliers/SUP001/scorecard"
    )

    assert response.status_code == 200

    body = response.json()

    # INV1001:
    # Jul 23 - Jul 20 = 3 days
    #
    # INV1002:
    # Jul 25 - Jul 20 = 5 days
    #
    # Average = 4 days

    assert (
        body["details"]["invoices"]
        ["average_cycle_time_days"]
        == 4.0
    )


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
            "rating": "Good",
            "performance_status": "Healthy",
        },

        "score_breakdown": {
            "on_time_delivery": {
                "score": 50.0,
                "weight_percentage": 40.0,
                "weighted_score": 20.0,
            },
            "invoice_accuracy": {
                "score": 100.0,
                "weight_percentage": 40.0,
                "weighted_score": 40.0,
            },
            "dispute_performance": {
                "score": 100.0,
                "weight_percentage": 20.0,
                "weighted_score": 20.0,
            },
        },

        "details": {
            "purchase_orders": {
                "total": 2,
                "fulfilled": 1,
                "on_time": 1,
                "late": 0,
                "pending": 1,
                "cancelled": 0,
                "on_time_percentage": 50.0,
                "late_percentage": 0.0,
                "fulfillment_rate": 50.0,
                "average_delay_days": 0.0,
            },

            "invoices": {
                "total": 1,
                "disputed": 0,
                "accurate": 1,
                "inaccurate": 0,
                "approved": 0,
                "rejected": 0,
                "pending": 1,
                "accuracy_percentage": 100.0,
                "dispute_rate_percentage": 0.0,
                "approval_rate_percentage": 0.0,
                "average_cycle_time_days": 3.0,
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
        model.scorecard.dispute_rate_percentage
        == 0.0
    )

    assert (
        model.scorecard.invoice_accuracy_percentage
        == 100.0
    )

    assert (
        model.scorecard.overall_score
        == 80.0
    )

    assert (
        model.scorecard.rating
        == "Good"
    )

    assert (
        model.scorecard.performance_status
        == "Healthy"
    )

    assert (
        model.score_breakdown.on_time_delivery.weighted_score
        == 20.0
    )

    assert (
        model.score_breakdown.invoice_accuracy.weighted_score
        == 40.0
    )

    assert (
        model.score_breakdown.dispute_performance.weighted_score
        == 20.0
    )

    assert (
        model.details.purchase_orders.pending
        == 1
    )

    assert (
        model.details.purchase_orders.cancelled
        == 0
    )

    assert (
        model.details.purchase_orders.fulfillment_rate
        == 50.0
    )

    assert (
        model.details.invoices.pending
        == 1
    )

    assert (
        model.details.invoices.accuracy_percentage
        == 100.0
    )

    assert (
        model.details.invoices.average_cycle_time_days
        == 3.0
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