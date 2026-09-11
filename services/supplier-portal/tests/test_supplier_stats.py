from datetime import date

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.main import app
from app.core.auth import verify_token
from app.services.purchase_order_service import purchase_orders
from app.services.invoice_service import invoices
from app.services.goods_receipt_service import goods_receipts
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
    goods_receipts.clear()
    app.dependency_overrides.clear()

    authenticate_as(SUPPLIER_1_USER)


# ============================================================
# SAMPLE AUTHENTICATED USERS
# ============================================================


SUPPLIER_1_USER = {
    "valid": True,
    "user_id": 8,
    "email": "supplier@company.com",
    "full_name": "Supplier User",
    "role": "supplier",
    "supplier_id": "SUP001",
    "is_active": True,
}


SUPPLIER_2_USER = {
    "valid": True,
    "user_id": 9,
    "email": "supplier2@company.com",
    "full_name": "Supplier Two",
    "role": "supplier",
    "supplier_id": "SUP002",
    "is_active": True,
}


PROCUREMENT_USER = {
    "valid": True,
    "user_id": 4,
    "email": "procurementmanager@company.com",
    "full_name": "Procurement Manager",
    "role": "procurement_manager",
    "supplier_id": None,
    "is_active": True,
}


COMPLIANCE_USER = {
    "valid": True,
    "user_id": 6,
    "email": "compliance@company.com",
    "full_name": "Compliance Officer",
    "role": "compliance_officer",
    "supplier_id": None,
    "is_active": True,
}


# ============================================================
# AUTHENTICATION HELPER
# ============================================================


def authenticate_as(user):
    """
    Override the real Platform authentication dependency
    for supplier stats/scorecard tests.
    """

    async def mock_verify_token():
        return user

    app.dependency_overrides[verify_token] = mock_verify_token


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

    goods_receipts["GR1001"] = {
        "receipt_id": "GR1001",
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "receipt_date": date(2026, 7, 27),
        "warehouse": "WH001",
        "received_by": "Warehouse User",
        "items": [],
        "status": "received",
        "created_at": "2026-07-27T10:00:00",
        "created_by": "warehouse@company.com",
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

    assert (
        body["scorecard"]["on_time_delivery_percentage"]
        == 50.0
    )

    assert (
        body["scorecard"]["dispute_rate_percentage"]
        == 0.0
    )

    assert (
        body["scorecard"]["invoice_accuracy_percentage"]
        == 100.0
    )

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
    assert (po_details["average_fulfillment_time_days"] == 7.0
)

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
                "average_fulfillment_time_days": 8.0,
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

        "trend": [
            {
                "period": "2026-07",
                "on_time_percentage": 50.0,
                "dispute_rate_percentage": 0.0,
                "invoice_accuracy_percentage": 100.0,
                "average_fulfillment_time_days": 8.0,
            }
        ],
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
        model.score_breakdown
        .on_time_delivery
        .weighted_score
        == 20.0
    )

    assert (
        model.score_breakdown
        .invoice_accuracy
        .weighted_score
        == 40.0
    )

    assert (
        model.score_breakdown
        .dispute_performance
        .weighted_score
        == 20.0
    )

    assert (
        model.details
        .purchase_orders
        .pending
        == 1
    )

    assert (
        model.details
        .purchase_orders
        .cancelled
        == 0
    )

    assert (
        model.details
        .purchase_orders
        .fulfillment_rate
        == 50.0
    )

    assert (
        model.details
        .purchase_orders
        .average_fulfillment_time_days
        == 8.0
    )

    assert (
        model.details
        .invoices
        .pending
        == 1
    )

    assert (
        model.details
        .invoices
        .accuracy_percentage
        == 100.0
    )

    assert (
        model.details
        .invoices
        .average_cycle_time_days
        == 3.0
    )

    assert len(model.trend) == 1

    assert (
        model.trend[0].period
        == "2026-07"
    )

    assert (
        model.trend[0].on_time_percentage
        == 50.0
    )

    assert (
        model.trend[0].dispute_rate_percentage
        == 0.0
    )

    assert (
        model.trend[0].invoice_accuracy_percentage
        == 100.0
    )

    assert (
        model.trend[0].average_fulfillment_time_days
        == 8.0
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


# ============================================================
# R5 - SUPPLIER AUTHENTICATION & SUPPLIER SCOPING
# ============================================================


def test_r5_supplier_can_access_own_stats():
    """
    R5:
    Supplier SUP001 can access its own statistics.
    """

    purchase_orders["PO-SUP001-001"] = {
        "po_number": "PO-SUP001-001",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-08-01T10:00:00",
        "expected_delivery": date(2026, 8, 10),
        "actual_delivery_date": date(2026, 8, 9),
    }

    authenticate_as(SUPPLIER_1_USER)

    try:
        response = client.get(
            "/api/v1/suppliers/SUP001/stats"
        )

        assert response.status_code == 200

        body = response.json()

        assert body["supplier_id"] == "SUP001"

    finally:
        app.dependency_overrides.clear()


def test_r5_supplier_cannot_access_other_supplier_stats():
    """
    R5:
    Supplier SUP001 cannot access SUP002 statistics.
    """

    purchase_orders["PO-SUP002-001"] = {
        "po_number": "PO-SUP002-001",
        "supplier_id": "SUP002",
        "status": "fulfilled",
        "created_at": "2026-08-01T10:00:00",
        "expected_delivery": date(2026, 8, 10),
        "actual_delivery_date": date(2026, 8, 9),
    }

    authenticate_as(SUPPLIER_1_USER)

    try:
        response = client.get(
            "/api/v1/suppliers/SUP002/stats"
        )

        assert response.status_code == 403

        assert response.json()["detail"] == (
            "You are not authorized to access this supplier"
        )

    finally:
        app.dependency_overrides.clear()


def test_r5_supplier_can_access_own_scorecard():
    """
    R5:
    Supplier SUP001 can access its own scorecard.
    """

    purchase_orders["PO-SUP001-001"] = {
        "po_number": "PO-SUP001-001",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-08-01T10:00:00",
        "expected_delivery": date(2026, 8, 10),
        "actual_delivery_date": date(2026, 8, 9),
    }

    authenticate_as(SUPPLIER_1_USER)

    try:
        response = client.get(
            "/api/v1/suppliers/SUP001/scorecard"
        )

        assert response.status_code == 200

        body = response.json()

        assert body["supplier_id"] == "SUP001"

    finally:
        app.dependency_overrides.clear()


def test_r5_supplier_cannot_access_other_supplier_scorecard():
    """
    R5:
    Supplier SUP001 cannot access SUP002 scorecard.
    """

    purchase_orders["PO-SUP002-001"] = {
        "po_number": "PO-SUP002-001",
        "supplier_id": "SUP002",
        "status": "fulfilled",
        "created_at": "2026-08-01T10:00:00",
        "expected_delivery": date(2026, 8, 10),
        "actual_delivery_date": date(2026, 8, 9),
    }

    authenticate_as(SUPPLIER_1_USER)

    try:
        response = client.get(
            "/api/v1/suppliers/SUP002/scorecard"
        )

        assert response.status_code == 403

        assert response.json()["detail"] == (
            "You are not authorized to access this supplier"
        )

    finally:
        app.dependency_overrides.clear()


def test_r5_supplier_2_can_access_own_stats():
    """
    R5:
    Supplier SUP002 can access its own statistics.
    """

    purchase_orders["PO-SUP002-001"] = {
        "po_number": "PO-SUP002-001",
        "supplier_id": "SUP002",
        "status": "fulfilled",
        "created_at": "2026-08-01T10:00:00",
        "expected_delivery": date(2026, 8, 10),
        "actual_delivery_date": date(2026, 8, 10),
    }

    authenticate_as(SUPPLIER_2_USER)

    try:
        response = client.get(
            "/api/v1/suppliers/SUP002/stats"
        )

        assert response.status_code == 200

        body = response.json()

        assert body["supplier_id"] == "SUP002"

    finally:
        app.dependency_overrides.clear()


def test_r5_supplier_2_cannot_access_supplier_1_stats():
    """
    R5:
    Supplier SUP002 cannot access SUP001 statistics.
    """

    purchase_orders["PO-SUP001-001"] = {
        "po_number": "PO-SUP001-001",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-08-01T10:00:00",
        "expected_delivery": date(2026, 8, 10),
        "actual_delivery_date": date(2026, 8, 9),
    }

    authenticate_as(SUPPLIER_2_USER)

    try:
        response = client.get(
            "/api/v1/suppliers/SUP001/stats"
        )

        assert response.status_code == 403

        assert response.json()["detail"] == (
            "You are not authorized to access this supplier"
        )

    finally:
        app.dependency_overrides.clear()

# ============================================================
# R5 - ADDITIONAL AUTHORIZATION / EDGE CASE TESTS
# ============================================================


def test_r5_supplier_missing_supplier_id_cannot_access_stats():
    """
    R5:
    A supplier token without supplier_id must not access
    supplier statistics.
    """

    supplier_without_id = {
        "valid": True,
        "user_id": 10,
        "email": "supplier-no-id@company.com",
        "full_name": "Supplier Without ID",
        "role": "supplier",
        "supplier_id": None,
        "is_active": True,
    }

    purchase_orders["PO-NOID-001"] = {
        "po_number": "PO-NOID-001",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-08-01T10:00:00",
        "expected_delivery": date(2026, 8, 10),
        "actual_delivery_date": date(2026, 8, 9),
    }

    authenticate_as(supplier_without_id)

    try:
        response = client.get(
            "/api/v1/suppliers/SUP001/stats"
        )

        assert response.status_code == 403

        assert response.json()["detail"] == (
            "Supplier identity is missing"
        )

    finally:
        app.dependency_overrides.clear()

def test_r5_supplier_missing_supplier_id_cannot_access_scorecard():
    """
    R5:
    A supplier token without supplier_id must not access
    supplier scorecard.
    """

    supplier_without_id = {
        "valid": True,
        "user_id": 10,
        "email": "supplier-no-id@company.com",
        "full_name": "Supplier Without ID",
        "role": "supplier",
        "supplier_id": None,
        "is_active": True,
    }

    purchase_orders["PO-NOID-002"] = {
        "po_number": "PO-NOID-002",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-08-01T10:00:00",
        "expected_delivery": date(2026, 8, 10),
        "actual_delivery_date": date(2026, 8, 9),
    }

    authenticate_as(supplier_without_id)

    try:
        response = client.get(
            "/api/v1/suppliers/SUP001/scorecard"
        )

        assert response.status_code == 403

        assert response.json()["detail"] == (
            "Supplier identity is missing"
        )

    finally:
        app.dependency_overrides.clear()

def test_r5_supplier_unknown_supplier_stats_returns_404():
    """
    R5:
    A supplier requesting a completely unknown supplier
    must receive 404.
    """

    authenticate_as(SUPPLIER_1_USER)

    try:
        response = client.get(
            "/api/v1/suppliers/SUP999/stats"
        )

        assert response.status_code == 404

        assert response.json()["detail"] == (
            "Supplier 'SUP999' not found."
        )

    finally:
        app.dependency_overrides.clear()


def test_r5_supplier_unknown_supplier_scorecard_returns_404():
    """
    R5:
    A supplier requesting a completely unknown supplier
    scorecard must receive 404.
    """

    authenticate_as(SUPPLIER_1_USER)

    try:
        response = client.get(
            "/api/v1/suppliers/SUP999/scorecard"
        )

        assert response.status_code == 404

        assert response.json()["detail"] == (
            "Supplier 'SUP999' not found."
        )

    finally:
        app.dependency_overrides.clear()


def test_r5_internal_role_can_access_other_supplier_stats():
    """
    R5:
    Internal authorized roles are not restricted by
    supplier ownership scoping.
    """

    purchase_orders["PO-SUP002-001"] = {
        "po_number": "PO-SUP002-001",
        "supplier_id": "SUP002",
        "status": "fulfilled",
        "created_at": "2026-08-01T10:00:00",
        "expected_delivery": date(2026, 8, 10),
        "actual_delivery_date": date(2026, 8, 9),
    }

    authenticate_as(PROCUREMENT_USER)

    try:
        response = client.get(
            "/api/v1/suppliers/SUP002/stats"
        )

        assert response.status_code == 200

        body = response.json()

        assert body["supplier_id"] == "SUP002"

    finally:
        app.dependency_overrides.clear()


def test_r5_internal_role_can_access_other_supplier_scorecard():
    """
    R5:
    Internal authorized roles can access another
    supplier's scorecard.
    """

    purchase_orders["PO-SUP002-001"] = {
        "po_number": "PO-SUP002-001",
        "supplier_id": "SUP002",
        "status": "fulfilled",
        "created_at": "2026-08-01T10:00:00",
        "expected_delivery": date(2026, 8, 10),
        "actual_delivery_date": date(2026, 8, 9),
    }

    authenticate_as(PROCUREMENT_USER)

    try:
        response = client.get(
            "/api/v1/suppliers/SUP002/scorecard"
        )

        assert response.status_code == 200

        body = response.json()

        assert body["supplier_id"] == "SUP002"

    finally:
        app.dependency_overrides.clear()


def test_supplier_scorecard_average_fulfillment_time():
    """
    Milestone 4:
    Average fulfillment time is calculated from
    PO creation date to Goods Receipt date.
    """

    create_sample_data()

    response = client.get(
        "/api/v1/suppliers/SUP001/scorecard"
    )

    assert response.status_code == 200

    body = response.json()

    po_details = body["details"]["purchase_orders"]

    # PO1001:
    # Jul 20 -> Jul 27 = 7 days
    assert (
        po_details["average_fulfillment_time_days"]
        == 7.0
    )

def test_supplier_scorecard_trend():
    """
    Milestone 4:
    Supplier performance is trended by PO creation month.
    """

    create_sample_data()

    # --------------------------------------------------------
    # Second fulfilled PO in July
    # --------------------------------------------------------

    purchase_orders["PO1003"] = {
        "po_number": "PO1003",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-07-25T10:00:00",
        "expected_delivery": date(2026, 8, 2),
        "actual_delivery_date": date(2026, 8, 1),
    }

    goods_receipts["GR1003"] = {
        "receipt_id": "GR1003",
        "po_number": "PO1003",
        "supplier_id": "SUP001",
        "receipt_date": date(2026, 7, 31),
        "warehouse": "WH001",
        "received_by": "Warehouse User",
        "items": [],
        "status": "received",
        "created_at": "2026-07-31T10:00:00",
        "created_by": "warehouse@company.com",
    }

    # --------------------------------------------------------
    # July invoice with dispute
    # --------------------------------------------------------

    invoices["INV1002"] = {
        "invoice_number": "INV1002",
        "po_number": "PO1003",
        "supplier_id": "SUP001",
        "invoice_date": "2026-07-30",
        "status": "approved",
        "dispute": {
            "reason": "Incorrect price"
        },
    }

    response = client.get(
        "/api/v1/suppliers/SUP001/scorecard"
    )

    assert response.status_code == 200

    body = response.json()

    trend = body["trend"]

    assert len(trend) == 1

    july = trend[0]

    assert july["period"] == "2026-07"

    # July has:
    # PO1001 fulfilled/on-time
    # PO1003 fulfilled/on-time
    #
    # 2 / 2 = 100%
    assert july["on_time_percentage"] == 100.0

    # July invoices:
    # INV1001 -> no dispute
    # INV1002 -> disputed
    #
    # 1 / 2 = 50%
    assert july["dispute_rate_percentage"] == 50.0

    # 1 accurate / 2 total = 50%
    assert july["invoice_accuracy_percentage"] == 50.0

    # PO1001:
    # Jul 20 -> Jul 27 = 7 days
    #
    # PO1003:
    # Jul 25 -> Jul 31 = 6 days
    #
    # Average = 6.5 days
    assert (
        july["average_fulfillment_time_days"]
        == 6.5
    )

def test_supplier_scorecard_trend_multiple_months():
    """
    Milestone 4:
    Supplier performance trend contains multiple
    monthly periods when supplier activity spans
    multiple months.
    """

    create_sample_data()

    # --------------------------------------------------------
    # August PO
    # --------------------------------------------------------

    purchase_orders["PO2001"] = {
        "po_number": "PO2001",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-08-05T10:00:00",
        "expected_delivery": date(2026, 8, 15),
        "actual_delivery_date": date(2026, 8, 18),
    }

    goods_receipts["GR2001"] = {
        "receipt_id": "GR2001",
        "po_number": "PO2001",
        "supplier_id": "SUP001",
        "receipt_date": date(2026, 8, 20),
        "warehouse": "WH001",
        "received_by": "Warehouse User",
        "items": [],
        "status": "received",
        "created_at": "2026-08-20T10:00:00",
        "created_by": "warehouse@company.com",
    }

    invoices["INV2001"] = {
        "invoice_number": "INV2001",
        "po_number": "PO2001",
        "supplier_id": "SUP001",
        "invoice_date": "2026-08-21",
        "status": "submitted",
        "dispute": None,
    }

    response = client.get(
        "/api/v1/suppliers/SUP001/scorecard"
    )

    assert response.status_code == 200

    body = response.json()

    trend = body["trend"]

    assert len(trend) == 2

    # Trend is sorted chronologically.
    assert trend[0]["period"] == "2026-07"
    assert trend[1]["period"] == "2026-08"

    # July data exists.
    assert (
        trend[0]["average_fulfillment_time_days"]
        == 7.0
    )

    # August:
    # Aug 5 -> Aug 20 = 15 days
    assert (
        trend[1]["average_fulfillment_time_days"]
        == 15.0
    )

    # August delivery was late.
    assert trend[1]["on_time_percentage"] == 0.0

    # August invoice has no dispute.
    assert trend[1]["dispute_rate_percentage"] == 0.0

    assert trend[1]["invoice_accuracy_percentage"] == 100.0

