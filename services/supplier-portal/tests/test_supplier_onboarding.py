import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import verify_token
from app.services.supplier_onboarding_service import (
    suppliers,
    supplier_documents,
    supplier_onboarding_history,
)


# ============================================================
# TEST USERS
# ============================================================

SUPPLIER_USER = {
    "valid": True,
    "user_id": 8,
    "email": "supplier@company.com",
    "full_name": "Supplier User",
    "role": "supplier",
    "supplier_id": "SUP001",
    "is_active": True,
}


SUPPLIER_B_USER = {
    "valid": True,
    "user_id": 99,
    "email": "supplierb@example.com",
    "full_name": "Supplier B",
    "role": "supplier",
    "supplier_id": "SUP002",
    "is_active": True,
}


SUPPLIER_NO_ID_USER = {
    "valid": True,
    "user_id": 100,
    "email": "supplier-no-id@example.com",
    "full_name": "Supplier Without ID",
    "role": "supplier",
    "supplier_id": None,
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


# ============================================================
# TEST DATA
# ============================================================

SUPPLIER_A_REGISTRATION = {
    "supplier_id": "SUP001",
    "company_name": "ABC Supplies Pvt Ltd",
    "contact_name": "Ravi Kumar",
    "email": "ravi@abcsupplies.com",
    "phone": "9876543210",
    "address": "Hyderabad, Telangana",
    "required_documents": [
        "gst_certificate",
        "pan_card",
        "bank_certificate",
    ],
}


SUPPLIER_B_REGISTRATION = {
    "supplier_id": "SUP002",
    "company_name": "XYZ Supplies Pvt Ltd",
    "contact_name": "Suresh Kumar",
    "email": "suresh@xyzsupplies.com",
    "phone": "9876543211",
    "address": "Hyderabad, Telangana",
    "required_documents": [
        "gst_certificate",
        "pan_card",
        "bank_certificate",
    ],
}


# ============================================================
# AUTHENTICATED CLIENT
# ============================================================

class AuthenticatedTestClient:
    """
    Simple wrapper around TestClient which changes the
    authentication user before every request.
    """

    def __init__(self, client, user):
        self.client = client
        self.user = user

    def request(self, method, url, **kwargs):
        async def mock_verify_token():
            return self.user

        app.dependency_overrides[verify_token] = (
            mock_verify_token
        )

        return self.client.request(
            method,
            url,
            **kwargs,
        )

    def get(self, url, **kwargs):
        return self.request(
            "GET",
            url,
            **kwargs,
        )

    def post(self, url, **kwargs):
        return self.request(
            "POST",
            url,
            **kwargs,
        )


# ============================================================
# FIXTURE
# ============================================================

@pytest.fixture(autouse=True)
def clean_onboarding_storage():
    """
    Reset supplier onboarding in-memory storage before and
    after every test.
    """

    suppliers.clear()
    supplier_documents.clear()
    supplier_onboarding_history.clear()

    yield

    suppliers.clear()
    supplier_documents.clear()
    supplier_onboarding_history.clear()


@pytest.fixture
def client():
    """
    Base TestClient.
    """

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(
        verify_token,
        None,
    )


@pytest.fixture
def supplier_client(client):
    return AuthenticatedTestClient(
        client,
        SUPPLIER_USER,
    )


@pytest.fixture
def supplier_b_client(client):
    return AuthenticatedTestClient(
        client,
        SUPPLIER_B_USER,
    )


@pytest.fixture
def supplier_no_id_client(client):
    return AuthenticatedTestClient(
        client,
        SUPPLIER_NO_ID_USER,
    )


@pytest.fixture
def procurement_client(client):
    return AuthenticatedTestClient(
        client,
        PROCUREMENT_USER,
    )


# ============================================================
# HELPERS
# ============================================================

def register_supplier(
    procurement_client,
    registration=SUPPLIER_A_REGISTRATION,
):
    return procurement_client.post(
        "/api/v1/suppliers/register",
        json=registration,
    )


def upload_document(
    supplier_client,
    supplier_id,
    document_type,
):
    """
    Upload a supplier document using multipart/form-data.

    document_type is sent as a form field using data=.
    """

    return supplier_client.post(
        f"/api/v1/suppliers/{supplier_id}/documents",
        data={
            "document_type": document_type,
        },
        files={
            "file": (
                f"{document_type}.pdf",
                io.BytesIO(
                    b"%PDF-1.4 test supplier document"
                ),
                "application/pdf",
            )
        },
    )


def upload_empty_document(
    supplier_client,
    supplier_id,
    document_type,
):
    """
    Upload an empty document to test validation.
    """

    return supplier_client.post(
        f"/api/v1/suppliers/{supplier_id}/documents",
        data={
            "document_type": document_type,
        },
        files={
            "file": (
                "empty.pdf",
                io.BytesIO(b""),
                "application/pdf",
            )
        },
    )


def register_supplier_b(procurement_client):
    return register_supplier(
        procurement_client,
        SUPPLIER_B_REGISTRATION,
    )


def submit_all_required_documents(
    supplier_client,
    supplier_id="SUP001",
):
    """
    Submit all required supplier documents.
    """

    for document_type in [
        "gst_certificate",
        "pan_card",
        "bank_certificate",
    ]:
        response = upload_document(
            supplier_client,
            supplier_id,
            document_type,
        )

        assert response.status_code == 201


def complete_verification(
    procurement_client,
    supplier_client,
    supplier_id="SUP001",
):
    """
    Register supplier, upload all documents,
    and complete verification.
    """

    registration = (
        SUPPLIER_A_REGISTRATION
        if supplier_id == "SUP001"
        else SUPPLIER_B_REGISTRATION
    )

    register_response = register_supplier(
        procurement_client,
        registration,
    )

    assert register_response.status_code == 201

    submit_all_required_documents(
        supplier_client,
        supplier_id,
    )

    verify_response = procurement_client.post(
        f"/api/v1/suppliers/{supplier_id}/verify"
    )

    assert verify_response.status_code == 201

    return verify_response


def complete_approval(
    procurement_client,
    supplier_client,
    supplier_id="SUP001",
):
    """
    Register supplier, upload documents,
    verify and approve the supplier.
    """

    complete_verification(
        procurement_client,
        supplier_client,
        supplier_id,
    )

    response = procurement_client.post(
        f"/api/v1/suppliers/{supplier_id}/approve",
        json={
            "reason": "Approved after successful verification",
        },
    )

    assert response.status_code == 201

    return response


# ============================================================
# 1. REGISTER SUPPLIER
# ============================================================

def test_register_supplier(procurement_client):
    response = register_supplier(
        procurement_client
    )

    assert response.status_code == 201

    data = response.json()

    assert data["supplier_id"] == "SUP001"

    assert data["company_name"] == (
        "ABC Supplies Pvt Ltd"
    )

    assert data["status"] == (
        "pending_documents"
    )

    assert data["required_documents"] == [
        "gst_certificate",
        "pan_card",
        "bank_certificate",
    ]


# ============================================================
# 2. DUPLICATE REGISTRATION
# ============================================================

def test_register_duplicate_supplier(
    procurement_client,
):
    first_response = register_supplier(
        procurement_client
    )

    assert first_response.status_code == 201

    second_response = register_supplier(
        procurement_client
    )

    assert second_response.status_code == 400

    assert (
        "already registered"
        in second_response.json()["detail"]
    )


# ============================================================
# 3. SUPPLIER CAN VIEW OWN DETAILS
# ============================================================

def test_supplier_can_view_own_details(
    procurement_client,
    supplier_client,
):
    register_response = register_supplier(
        procurement_client
    )

    assert register_response.status_code == 201

    response = supplier_client.get(
        "/api/v1/suppliers/SUP001"
    )

    # GET endpoint -> 200
    assert response.status_code == 200

    data = response.json()

    assert data["supplier_id"] == "SUP001"

    assert data["status"] == (
        "pending_documents"
    )


# ============================================================
# 4. SUPPLIER CANNOT VIEW ANOTHER SUPPLIER
# ============================================================

def test_supplier_cannot_view_other_supplier(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    assert (
        register_supplier_b(
            procurement_client
        ).status_code
        == 201
    )

    response = supplier_client.get(
        "/api/v1/suppliers/SUP002"
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Supplier access is restricted to own data"
    )


# ============================================================
# 5. SUPPLIER CAN UPLOAD OWN DOCUMENT
# ============================================================

def test_supplier_can_upload_own_document(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    response = upload_document(
        supplier_client,
        "SUP001",
        "gst_certificate",
    )

    # POST upload -> 201
    assert response.status_code == 201

    data = response.json()

    assert data["supplier_id"] == "SUP001"

    assert data["document_type"] == (
        "gst_certificate"
    )

    assert data["status"] == "submitted"


# ============================================================
# 6. SUPPLIER CANNOT UPLOAD OTHER SUPPLIER DOCUMENT
# ============================================================

def test_supplier_cannot_upload_other_supplier_document(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    assert (
        register_supplier_b(
            procurement_client
        ).status_code
        == 201
    )

    response = upload_document(
        supplier_client,
        "SUP002",
        "gst_certificate",
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Supplier access is restricted to own data"
    )


# ============================================================
# 7. INVALID DOCUMENT TYPE
# ============================================================

def test_invalid_document_type_rejected(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    response = upload_document(
        supplier_client,
        "SUP001",
        "invalid_document",
    )

    assert response.status_code == 400

    assert (
        "is not required"
        in response.json()["detail"]
    )


# ============================================================
# 8. EMPTY DOCUMENT
# ============================================================

def test_empty_document_rejected(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    response = upload_empty_document(
        supplier_client,
        "SUP001",
        "gst_certificate",
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Uploaded document is empty."
    )


# ============================================================
# 9. DUPLICATE DOCUMENT
# ============================================================

def test_duplicate_document_rejected(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    first_response = upload_document(
        supplier_client,
        "SUP001",
        "gst_certificate",
    )

    assert first_response.status_code == 201

    second_response = upload_document(
        supplier_client,
        "SUP001",
        "gst_certificate",
    )

    assert second_response.status_code == 400

    assert second_response.json()["detail"] == (
        "Document 'gst_certificate' "
        "has already been submitted."
    )


# ============================================================
# 10. STATUS AFTER ALL DOCUMENTS
# ============================================================

def test_status_changes_after_all_documents_submitted(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    submit_all_required_documents(
        supplier_client
    )

    response = supplier_client.get(
        "/api/v1/suppliers/SUP001/status"
    )

    # GET -> 200
    assert response.status_code == 200

    data = response.json()

    assert data["status"] == (
        "documents_submitted"
    )

    assert set(
        data["submitted_documents"]
    ) == {
        "gst_certificate",
        "pan_card",
        "bank_certificate",
    }

    assert data["missing_documents"] == []


# ============================================================
# 11. SUPPLIER CAN LIST OWN DOCUMENTS
# ============================================================

def test_supplier_can_list_own_documents(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    upload_response = upload_document(
        supplier_client,
        "SUP001",
        "gst_certificate",
    )

    assert upload_response.status_code == 201

    response = supplier_client.get(
        "/api/v1/suppliers/SUP001/documents"
    )

    # GET -> 200
    assert response.status_code == 200

    documents = response.json()

    assert len(documents) == 1

    assert documents[0]["supplier_id"] == (
        "SUP001"
    )

    assert documents[0]["document_type"] == (
        "gst_certificate"
    )


# ============================================================
# 12. SUPPLIER CANNOT LIST OTHER DOCUMENTS
# ============================================================

def test_supplier_cannot_list_other_supplier_documents(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    assert (
        register_supplier_b(
            procurement_client
        ).status_code
        == 201
    )

    response = supplier_client.get(
        "/api/v1/suppliers/SUP002/documents"
    )

    assert response.status_code == 403


# ============================================================
# 13. SUPPLIER CAN VIEW OWN STATUS
# ============================================================

def test_supplier_can_view_own_status(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    response = supplier_client.get(
        "/api/v1/suppliers/SUP001/status"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["supplier_id"] == "SUP001"

    assert data["status"] == (
        "pending_documents"
    )

    assert set(
        data["missing_documents"]
    ) == {
        "gst_certificate",
        "pan_card",
        "bank_certificate",
    }


# ============================================================
# 14. SUPPLIER CANNOT VIEW OTHER STATUS
# ============================================================

def test_supplier_cannot_view_other_supplier_status(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    assert (
        register_supplier_b(
            procurement_client
        ).status_code
        == 201
    )

    response = supplier_client.get(
        "/api/v1/suppliers/SUP002/status"
    )

    assert response.status_code == 403


# ============================================================
# 15. PROCUREMENT MANAGER CAN VERIFY SUPPLIER
# ============================================================

def test_procurement_manager_can_verify_supplier(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    submit_all_required_documents(
        supplier_client
    )

    response = procurement_client.post(
        "/api/v1/suppliers/SUP001/verify"
    )

    # POST verify -> 201
    assert response.status_code == 201

    data = response.json()

    assert data["supplier_id"] == "SUP001"

    assert data["status"] == "verified"

    assert data["verification_result"] == (
        "passed"
    )


# ============================================================
# 16. SUPPLIER CANNOT VERIFY
# ============================================================

def test_supplier_cannot_verify(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    submit_all_required_documents(
        supplier_client
    )

    response = supplier_client.post(
        "/api/v1/suppliers/SUP001/verify"
    )

    assert response.status_code == 403


# ============================================================
# 17. VERIFICATION REQUIRES DOCUMENTS
# ============================================================

def test_verification_requires_all_documents(
    procurement_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    response = procurement_client.post(
        "/api/v1/suppliers/SUP001/verify"
    )

    assert response.status_code == 400

    assert (
        "must have all required documents"
        in response.json()["detail"]
    )


# ============================================================
# 18. PROCUREMENT MANAGER CAN APPROVE SUPPLIER
# ============================================================

def test_procurement_manager_can_approve_supplier(
    procurement_client,
    supplier_client,
):
    complete_verification(
        procurement_client,
        supplier_client,
    )

    response = procurement_client.post(
        "/api/v1/suppliers/SUP001/approve",
        json={
            "reason": (
                "Supplier documents and "
                "verification completed successfully"
            )
        },
    )

    # POST approve -> 201
    assert response.status_code == 201

    data = response.json()

    assert data["supplier_id"] == "SUP001"

    assert data["status"] == "approved"

    assert data["reason"] == (
        "Supplier documents and "
        "verification completed successfully"
    )


# ============================================================
# 19. SUPPLIER CANNOT APPROVE
# ============================================================

def test_supplier_cannot_approve(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    response = supplier_client.post(
        "/api/v1/suppliers/SUP001/approve",
        json={
            "reason": "Not authorized",
        },
    )

    assert response.status_code == 403


# ============================================================
# 20. PROCUREMENT MANAGER CAN ACTIVATE SUPPLIER
# ============================================================

def test_procurement_manager_can_activate_supplier(
    procurement_client,
    supplier_client,
):
    complete_approval(
        procurement_client,
        supplier_client,
    )

    response = procurement_client.post(
        "/api/v1/suppliers/SUP001/activate"
    )

    # POST activate -> 201
    assert response.status_code == 201

    data = response.json()

    assert data["supplier_id"] == "SUP001"

    assert data["status"] == "active"


# ============================================================
# 21. SUPPLIER CANNOT ACTIVATE
# ============================================================

def test_supplier_cannot_activate(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    response = supplier_client.post(
        "/api/v1/suppliers/SUP001/activate"
    )

    assert response.status_code == 403


# ============================================================
# 22. CANNOT APPROVE BEFORE VERIFICATION
# ============================================================

def test_cannot_approve_before_verification(
    procurement_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    response = procurement_client.post(
        "/api/v1/suppliers/SUP001/approve",
        json={
            "reason": "Premature approval",
        },
    )

    assert response.status_code == 400

    assert (
        "Cannot move supplier"
        in response.json()["detail"]
    )


# ============================================================
# 23. CANNOT ACTIVATE BEFORE APPROVAL
# ============================================================

def test_cannot_activate_before_approval(
    procurement_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    response = procurement_client.post(
        "/api/v1/suppliers/SUP001/activate"
    )

    assert response.status_code == 400

    assert (
        "Cannot move supplier"
        in response.json()["detail"]
    )


# ============================================================
# 24. ACTIVE SUPPLIER CANNOT BE ACTIVATED AGAIN
# ============================================================

def test_active_supplier_cannot_be_activated_again(
    procurement_client,
    supplier_client,
):
    complete_approval(
        procurement_client,
        supplier_client,
    )

    first_activation = procurement_client.post(
        "/api/v1/suppliers/SUP001/activate"
    )

    assert first_activation.status_code == 201

    second_activation = procurement_client.post(
        "/api/v1/suppliers/SUP001/activate"
    )

    assert second_activation.status_code == 400


# ============================================================
# 25. SUPPLIER CAN VIEW OWN HISTORY
# ============================================================

def test_supplier_can_view_own_history(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    response = supplier_client.get(
        "/api/v1/suppliers/SUP001/history"
    )

    assert response.status_code == 200

    history = response.json()

    assert len(history) == 1

    assert history[0]["supplier_id"] == (
        "SUP001"
    )

    assert history[0]["from_status"] is None

    assert history[0]["to_status"] == (
        "pending_documents"
    )


# ============================================================
# 26. SUPPLIER CANNOT VIEW OTHER HISTORY
# ============================================================

def test_supplier_cannot_view_other_supplier_history(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    assert (
        register_supplier_b(
            procurement_client
        ).status_code
        == 201
    )

    response = supplier_client.get(
        "/api/v1/suppliers/SUP002/history"
    )

    assert response.status_code == 403


# ============================================================
# 27. PROCUREMENT MANAGER CAN LIST SUPPLIERS
# ============================================================

def test_procurement_manager_can_list_suppliers(
    procurement_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    assert (
        register_supplier_b(
            procurement_client
        ).status_code
        == 201
    )

    response = procurement_client.get(
        "/api/v1/suppliers"
    )

    # GET -> 200
    assert response.status_code == 200

    suppliers_response = response.json()

    assert len(suppliers_response) == 2

    supplier_ids = {
        item["supplier_id"]
        for item in suppliers_response
    }

    assert supplier_ids == {
        "SUP001",
        "SUP002",
    }


# ============================================================
# 28. SUPPLIER CANNOT LIST ALL SUPPLIERS
# ============================================================

def test_supplier_cannot_list_all_suppliers(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    response = supplier_client.get(
        "/api/v1/suppliers"
    )

    assert response.status_code == 403


# ============================================================
# 29. SUPPLIER WITHOUT SUPPLIER ID
# ============================================================

def test_supplier_without_supplier_id_is_rejected(
    supplier_no_id_client,
):
    response = supplier_no_id_client.get(
        "/api/v1/suppliers/SUP001"
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Supplier identity could not be resolved"
    )


# ============================================================
# 30. COMPLETE ONBOARDING WORKFLOW
# ============================================================

def test_complete_supplier_onboarding_workflow(
    procurement_client,
    supplier_client,
):
    # --------------------------------------------------------
    # Registration
    # --------------------------------------------------------

    register_response = register_supplier(
        procurement_client
    )

    assert register_response.status_code == 201

    assert (
        register_response.json()["status"]
        == "pending_documents"
    )

    # --------------------------------------------------------
    # Document collection
    # --------------------------------------------------------

    submit_all_required_documents(
        supplier_client
    )

    status_response = supplier_client.get(
        "/api/v1/suppliers/SUP001/status"
    )

    # GET -> 200
    assert status_response.status_code == 200

    assert (
        status_response.json()["status"]
        == "documents_submitted"
    )

    # --------------------------------------------------------
    # Mock verification
    # --------------------------------------------------------

    verify_response = procurement_client.post(
        "/api/v1/suppliers/SUP001/verify"
    )

    # POST -> 201
    assert verify_response.status_code == 201

    assert (
        verify_response.json()["status"]
        == "verified"
    )

    assert (
        verify_response.json()["verification_result"]
        == "passed"
    )

    # --------------------------------------------------------
    # Approval
    # --------------------------------------------------------

    approve_response = procurement_client.post(
        "/api/v1/suppliers/SUP001/approve",
        json={
            "reason": (
                "Verification completed successfully"
            ),
        },
    )

    # POST -> 201
    assert approve_response.status_code == 201

    assert (
        approve_response.json()["status"]
        == "approved"
    )

    # --------------------------------------------------------
    # Activation
    # --------------------------------------------------------

    activate_response = procurement_client.post(
        "/api/v1/suppliers/SUP001/activate"
    )

    # POST -> 201
    assert activate_response.status_code == 201

    assert (
        activate_response.json()["status"]
        == "active"
    )

    # --------------------------------------------------------
    # Final status
    # --------------------------------------------------------

    final_status = supplier_client.get(
        "/api/v1/suppliers/SUP001/status"
    )

    # GET -> 200
    assert final_status.status_code == 200

    assert (
        final_status.json()["status"]
        == "active"
    )

    # --------------------------------------------------------
    # History
    # --------------------------------------------------------

    history_response = supplier_client.get(
        "/api/v1/suppliers/SUP001/history"
    )

    # GET -> 200
    assert history_response.status_code == 200

    history = history_response.json()

    assert len(history) == 5

    statuses = [
        item["to_status"]
        for item in history
    ]

    assert statuses == [
        "pending_documents",
        "documents_submitted",
        "verified",
        "approved",
        "active",
    ]

# ============================================================
# 31. SUPPLIER B CAN VIEW OWN DETAILS
# ============================================================

def test_supplier_b_can_view_own_details(
    procurement_client,
    supplier_b_client,
):
    assert (
        register_supplier_b(
            procurement_client
        ).status_code
        == 201
    )

    response = supplier_b_client.get(
        "/api/v1/suppliers/SUP002"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["supplier_id"] == "SUP002"


# ============================================================
# 32. SUPPLIER WITHOUT ID CANNOT VIEW DOCUMENTS
# ============================================================

def test_supplier_without_supplier_id_cannot_view_documents(
    procurement_client,
    supplier_no_id_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    response = supplier_no_id_client.get(
        "/api/v1/suppliers/SUP001/documents"
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Supplier identity could not be resolved"
    )


# ============================================================
# 33. SUPPLIER WITHOUT ID CANNOT VIEW STATUS
# ============================================================

def test_supplier_without_supplier_id_cannot_view_status(
    procurement_client,
    supplier_no_id_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    response = supplier_no_id_client.get(
        "/api/v1/suppliers/SUP001/status"
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Supplier identity could not be resolved"
    )


# ============================================================
# 34. SUPPLIER WITHOUT ID CANNOT VIEW HISTORY
# ============================================================

def test_supplier_without_supplier_id_cannot_view_history(
    procurement_client,
    supplier_no_id_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    response = supplier_no_id_client.get(
        "/api/v1/suppliers/SUP001/history"
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Supplier identity could not be resolved"
    )


# ============================================================
# 35. UNKNOWN SUPPLIER DETAILS RETURN 404
# ============================================================

def test_unknown_supplier_details_return_404(
    supplier_client,
):
    response = supplier_client.get(
        "/api/v1/suppliers/UNKNOWN"
    )

    assert response.status_code == 404


# ============================================================
# 36. UNKNOWN SUPPLIER DOCUMENTS RETURN 404
# ============================================================

def test_unknown_supplier_documents_return_404(
    supplier_client,
):
    response = supplier_client.get(
        "/api/v1/suppliers/UNKNOWN/documents"
    )

    assert response.status_code == 404


# ============================================================
# 37. UNKNOWN SUPPLIER STATUS RETURNS 404
# ============================================================

def test_unknown_supplier_status_returns_404(
    supplier_client,
):
    response = supplier_client.get(
        "/api/v1/suppliers/UNKNOWN/status"
    )

    assert response.status_code == 404


# ============================================================
# 38. UNKNOWN SUPPLIER HISTORY RETURNS 404
# ============================================================

def test_unknown_supplier_history_returns_404(
    supplier_client,
):
    response = supplier_client.get(
        "/api/v1/suppliers/UNKNOWN/history"
    )

    assert response.status_code == 404


# ============================================================
# 39. PROCUREMENT MANAGER CAN VIEW SUPPLIER DETAILS
# ============================================================

def test_procurement_manager_can_view_supplier_details(
    procurement_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    response = procurement_client.get(
        "/api/v1/suppliers/SUP001"
    )

    assert response.status_code == 200

    assert response.json()["supplier_id"] == "SUP001"


# ============================================================
# 40. PROCUREMENT MANAGER CAN VIEW SUPPLIER STATUS
# ============================================================

def test_procurement_manager_can_view_supplier_status(
    procurement_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    response = procurement_client.get(
        "/api/v1/suppliers/SUP001/status"
    )

    assert response.status_code == 200

    assert response.json()["supplier_id"] == "SUP001"


# ============================================================
# 41. PROCUREMENT MANAGER CAN VIEW SUPPLIER HISTORY
# ============================================================

def test_procurement_manager_can_view_supplier_history(
    procurement_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    response = procurement_client.get(
        "/api/v1/suppliers/SUP001/history"
    )

    assert response.status_code == 200

    history = response.json()

    assert len(history) == 1

    assert history[0]["supplier_id"] == "SUP001"


# ============================================================
# 42. PROCUREMENT MANAGER CAN VIEW SUPPLIER DOCUMENTS
# ============================================================

def test_procurement_manager_can_view_supplier_documents(
    procurement_client,
    supplier_client,
):
    assert (
        register_supplier(
            procurement_client
        ).status_code
        == 201
    )

    assert (
        upload_document(
            supplier_client,
            "SUP001",
            "gst_certificate",
        ).status_code
        == 201
    )

    response = procurement_client.get(
        "/api/v1/suppliers/SUP001/documents"
    )

    assert response.status_code == 200

    documents = response.json()

    assert len(documents) == 1

    assert documents[0]["supplier_id"] == "SUP001"

