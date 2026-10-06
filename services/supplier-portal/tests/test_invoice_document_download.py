"""
Comprehensive tests for the invoice document download endpoint.

Endpoint under test:
    GET /api/v1/invoices/{supplier_id}/{invoice_number}/document

These tests intentionally seed the in-memory invoice store directly.
The purpose of this test module is to validate document-download behavior,
authorization, supplier scoping, MinIO interaction, and error handling.

Purchase-order creation/onboarding is deliberately not exercised here because
it is outside the responsibility of the document-download endpoint.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import verify_token
from app.services import invoice_service
from app.services.invoice_service import invoices
from app.services.document_storage_service import (
    DocumentDownloadError,
    DocumentStorageError,
)


client = TestClient(app)


# ============================================================================
# AUTHENTICATED TEST USERS
# ============================================================================

SUPPLIER_1_USER = {
    "user_id": 8,
    "role": "supplier",
    "supplier_id": "SUP001",
}

SUPPLIER_2_USER = {
    "user_id": 99,
    "role": "supplier",
    "supplier_id": "SUP002",
}

SUPPLIER_WITHOUT_ID_USER = {
    "user_id": 100,
    "role": "supplier",
}

PROCUREMENT_USER = {
    "user_id": 4,
    "role": "procurement_manager",
}

COMPLIANCE_USER = {
    "user_id": 6,
    "role": "compliance_officer",
}


# ============================================================================
# TEST HELPERS
# ============================================================================


def authenticate_as(user):
    """
    Override Platform authentication for the current test.
    """

    async def mock_verify_token():
        return user

    app.dependency_overrides[verify_token] = mock_verify_token


def invoice_object_key(
    supplier_id: str,
    invoice_number: str,
) -> str:
    """
    Build the expected supplier-scoped MinIO invoice object key.
    """

    return (
        f"suppliers/{supplier_id}/"
        f"invoices/{invoice_number}.pdf"
    )


def register_invoice_document(
    invoice_number: str = "INV1001",
    supplier_id: str = "SUP001",
    document_path: str | None = None,
):
    """
    Register an invoice directly in the in-memory store with a document path.

    This avoids unrelated PO/onboarding setup and keeps the tests focused
    on document-download behavior.
    """

    if document_path is None:
        document_path = invoice_object_key(
            supplier_id=supplier_id,
            invoice_number=invoice_number,
        )

    invoices[(supplier_id, invoice_number)] = {
        "invoice_number": invoice_number,
        "supplier_id": supplier_id,
        "document_path": document_path,
        "document_url": (
            f"/api/v1/invoices/"
            f"{supplier_id}/"
            f"{invoice_number}/document"
        ),
        "status": "submitted",
    }

    return invoices[(supplier_id, invoice_number)]


# ============================================================================
# TEST FIXTURE
# ============================================================================


@pytest.fixture(autouse=True)
def reset_data():
    """
    Reset invoice state and dependency overrides before and after every test.
    """

    invoices.clear()
    app.dependency_overrides.clear()

    yield

    invoices.clear()
    app.dependency_overrides.clear()


# ============================================================================
# 1. SUCCESSFUL DOWNLOAD
# ============================================================================


def test_invoice_document_download_success():
    """
    A supplier can generate a presigned download URL for its own invoice.
    """

    authenticate_as(SUPPLIER_1_USER)

    register_invoice_document(
        invoice_number="INV1001",
        supplier_id="SUP001",
    )

    expected_key = (
        "suppliers/SUP001/invoices/INV1001.pdf"
    )

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
        return_value=True,
    ) as mock_exists:
        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
            return_value=(
                "http://127.0.0.1:9000/"
                "supplier-documents/"
                "suppliers/SUP001/invoices/INV1001.pdf"
                "?X-Amz-Signature=test"
            ),
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP001/INV1001/document"
            )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["invoice_number"] == "INV1001"
    assert data["supplier_id"] == "SUP001"
    assert data["file_name"] == "INV1001.pdf"
    assert data["download_url"].startswith(
        "http://127.0.0.1:9000/"
    )
    assert data["expires_in_seconds"] == 300

    mock_exists.assert_called_once_with(
        object_key=expected_key,
    )

    mock_download.assert_called_once_with(
        object_key=expected_key,
    )


# ============================================================================
# 2. REGISTERED DOCUMENT PATH IS USED
# ============================================================================


def test_invoice_document_download_uses_registered_document_path():
    """
    The endpoint must use the document_path stored on the invoice instead
    of rebuilding or guessing a different path.
    """

    authenticate_as(SUPPLIER_1_USER)

    registered_path = (
        "suppliers/SUP001/invoices/custom-invoice-object.pdf"
    )

    register_invoice_document(
        invoice_number="INV1002",
        supplier_id="SUP001",
        document_path=registered_path,
    )

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
        return_value=True,
    ) as mock_exists:
        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
            return_value="https://minio.example/download",
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP001/INV1002/document"
            )

    assert response.status_code == 200, response.text

    mock_exists.assert_called_once_with(
        object_key=registered_path,
    )

    mock_download.assert_called_once_with(
        object_key=registered_path,
    )


# ============================================================================
# 3. CROSS-SUPPLIER ACCESS
# ============================================================================


def test_supplier_cannot_download_other_supplier_invoice_document():
    """
    SUP001 must not download a SUP002 invoice document.
    """

    authenticate_as(SUPPLIER_1_USER)

    register_invoice_document(
        invoice_number="INV2001",
        supplier_id="SUP002",
    )

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
    ) as mock_exists:
        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP002/INV2001/document"
            )

    assert response.status_code == 403, response.text

    assert (
        response.json()["detail"]
        == "Forbidden: supplier does not own this invoice"
    )

    mock_exists.assert_not_called()
    mock_download.assert_not_called()


# ============================================================================
# 4. CROSS-SUPPLIER ACCESS MUST NOT CALL MINIO
# ============================================================================


def test_cross_supplier_download_does_not_call_minio():
    """
    Authorization must happen before any MinIO operation.
    """

    authenticate_as(SUPPLIER_1_USER)

    register_invoice_document(
        invoice_number="INV2002",
        supplier_id="SUP002",
    )

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
    ) as mock_exists:
        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP002/INV2002/document"
            )

    assert response.status_code == 403

    mock_exists.assert_not_called()
    mock_download.assert_not_called()


# ============================================================================
# 5. UNKNOWN INVOICE
# ============================================================================


def test_invoice_document_download_unknown_invoice_returns_404():
    """
    A valid supplier requesting an invoice that does not exist receives 404.
    """

    authenticate_as(SUPPLIER_1_USER)

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
    ) as mock_exists:
        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP001/UNKNOWN/document"
            )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Invoice not found."

    mock_exists.assert_not_called()
    mock_download.assert_not_called()


# ============================================================================
# 6. INVOICE WITHOUT DOCUMENT
# ============================================================================


def test_invoice_document_download_without_document_returns_404():
    """
    An existing invoice without document_path must return 404.
    """

    authenticate_as(SUPPLIER_1_USER)

    invoices[("SUP001", "INV3001")] = {
        "invoice_number": "INV3001",
        "supplier_id": "SUP001",
        "document_path": None,
        "document_url": None,
        "status": "submitted",
    }

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
    ) as mock_exists:
        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP001/INV3001/document"
            )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Document not found."

    mock_exists.assert_not_called()
    mock_download.assert_not_called()


# ============================================================================
# 7. DOCUMENT PATH IS REGISTERED BUT OBJECT IS MISSING
# ============================================================================


def test_invoice_document_download_missing_minio_object_returns_404():
    """
    If the invoice points to an object that does not exist in MinIO,
    the endpoint must return 404.
    """

    authenticate_as(SUPPLIER_1_USER)

    register_invoice_document(
        invoice_number="INV3002",
        supplier_id="SUP001",
    )

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
        return_value=False,
    ) as mock_exists:
        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP001/INV3002/document"
            )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "File does not exist."

    mock_exists.assert_called_once()
    mock_download.assert_not_called()


# ============================================================================
# 8. MISSING OBJECT MUST NOT GENERATE PRESIGNED URL
# ============================================================================


def test_missing_minio_object_does_not_generate_download_url():
    """
    The presigned URL must only be generated after object existence
    has been confirmed.
    """

    authenticate_as(SUPPLIER_1_USER)

    register_invoice_document(
        invoice_number="INV3003",
        supplier_id="SUP001",
    )

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
        return_value=False,
    ):
        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP001/INV3003/document"
            )

    assert response.status_code == 404

    mock_download.assert_not_called()


# ============================================================================
# 9. MINIO OBJECT-EXISTS FAILURE
# ============================================================================


def test_invoice_document_download_object_exists_failure_returns_502():
    """
    A storage failure while checking object existence must be exposed as
    HTTP 502 rather than incorrectly reported as a missing file.
    """

    authenticate_as(SUPPLIER_1_USER)

    register_invoice_document(
        invoice_number="INV4001",
        supplier_id="SUP001",
    )

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
        side_effect=DocumentStorageError(
            "Unable to check document existence."
        ),
    ) as mock_exists:
        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP001/INV4001/document"
            )

    assert response.status_code == 502, response.text
    assert (
        response.json()["detail"]
        == "Unable to check document existence."
    )

    mock_exists.assert_called_once()
    mock_download.assert_not_called()


# ============================================================================
# 10. PRESIGNED URL GENERATION FAILURE
# ============================================================================


def test_invoice_document_download_presign_failure_returns_502():
    """
    If the object exists but MinIO fails to generate a presigned URL,
    the endpoint must return 502.
    """

    authenticate_as(SUPPLIER_1_USER)

    register_invoice_document(
        invoice_number="INV4002",
        supplier_id="SUP001",
    )

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
        return_value=True,
    ) as mock_exists:
        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
            side_effect=DocumentDownloadError(
                "Unable to generate document download URL."
            ),
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP001/INV4002/document"
            )

    assert response.status_code == 502, response.text
    assert (
        response.json()["detail"]
        == "Unable to generate document download URL."
    )

    mock_exists.assert_called_once()
    mock_download.assert_called_once()


# ============================================================================
# 11. AUTHENTICATION REQUIRED
# ============================================================================


def test_invoice_document_download_requires_authentication():
    """
    Missing authentication must be rejected.
    """

    response = client.get(
        "/api/v1/invoices/SUP001/INV5001/document"
    )

    assert response.status_code == 401, response.text


# ============================================================================
# 12. PROCUREMENT MANAGER ACCESS
# ============================================================================


def test_procurement_manager_can_download_invoice_document():
    """
    Procurement managers are not supplier-scoped users, so they can access
    the invoice document.
    """

    authenticate_as(PROCUREMENT_USER)

    register_invoice_document(
        invoice_number="INV5002",
        supplier_id="SUP001",
    )

    expected_key = (
        "suppliers/SUP001/invoices/INV5002.pdf"
    )

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
        return_value=True,
    ) as mock_exists:
        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
            return_value="https://minio.example/invoice",
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP001/INV5002/document"
            )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["invoice_number"] == "INV5002"
    assert data["supplier_id"] == "SUP001"
    assert data["file_name"] == "INV5002.pdf"

    mock_exists.assert_called_once_with(
        object_key=expected_key,
    )

    mock_download.assert_called_once_with(
        object_key=expected_key,
    )


# ============================================================================
# 13. SUPPLIER WITHOUT SUPPLIER_ID
# ============================================================================


def test_supplier_without_supplier_id_cannot_download_invoice_document():
    """
    A supplier token without supplier_id must be rejected with 403.
    """

    authenticate_as(SUPPLIER_WITHOUT_ID_USER)

    register_invoice_document(
        invoice_number="INV5003",
        supplier_id="SUP001",
    )

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
    ) as mock_exists:
        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP001/INV5003/document"
            )

    assert response.status_code == 403, response.text
    assert (
        response.json()["detail"]
        == "Supplier identity is missing"
    )

    mock_exists.assert_not_called()
    mock_download.assert_not_called()


# ============================================================================
# 14. SUPPLIER CAN DOWNLOAD OWN DOCUMENT
# ============================================================================


def test_supplier_can_download_own_invoice_document():
    """
    SUP001 can download a document belonging to SUP001.
    """

    authenticate_as(SUPPLIER_1_USER)

    register_invoice_document(
        invoice_number="INV6001",
        supplier_id="SUP001",
    )

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
        return_value=True,
    ) as mock_exists:
        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
            return_value="https://minio.example/own-invoice",
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP001/INV6001/document"
            )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["supplier_id"] == "SUP001"
    assert data["invoice_number"] == "INV6001"

    mock_exists.assert_called_once()
    mock_download.assert_called_once()


# ============================================================================
# 15. SUPPLIER B CANNOT ACCESS SUPPLIER A
# ============================================================================


def test_supplier_b_cannot_download_supplier_a_document():
    """
    SUP002 cannot access a document owned by SUP001.
    """

    authenticate_as(SUPPLIER_2_USER)

    register_invoice_document(
        invoice_number="INV6002",
        supplier_id="SUP001",
    )

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
    ) as mock_exists:
        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP001/INV6002/document"
            )

    assert response.status_code == 403, response.text
    assert (
        response.json()["detail"]
        == "Forbidden: supplier does not own this invoice"
    )

    mock_exists.assert_not_called()
    mock_download.assert_not_called()


# ============================================================================
# 16. REGISTERED SUPPLIER-SCOPED KEY
# ============================================================================


def test_invoice_document_download_uses_supplier_scoped_registered_key():
    """
    Verify that the document lookup remains supplier-scoped.

    Even when the invoice number is the same across suppliers, the object
    key must contain the correct supplier identifier.
    """

    authenticate_as(SUPPLIER_1_USER)

    register_invoice_document(
        invoice_number="INV7001",
        supplier_id="SUP001",
    )

    expected_key = (
        "suppliers/SUP001/invoices/INV7001.pdf"
    )

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
        return_value=True,
    ) as mock_exists:
        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
            return_value="https://minio.example/scoped",
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP001/INV7001/document"
            )

    assert response.status_code == 200, response.text

    mock_exists.assert_called_once_with(
        object_key=expected_key,
    )

    mock_download.assert_called_once_with(
        object_key=expected_key,
    )


# ============================================================================
# 17. INVALID INVOICE NUMBER
# ============================================================================


def test_invoice_document_download_invalid_invoice_number_returns_400():
    """
    Invalid invoice-number format is a Bad Request.

    The production invoice service validates the invoice number before
    accessing document storage.
    """

    authenticate_as(SUPPLIER_1_USER)

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
    ) as mock_exists:
        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP001/INVALID@INVOICE/document"
            )

    assert response.status_code == 400, response.text
    assert (
        response.json()["detail"]
        == "Invalid invoice number."
    )

    mock_exists.assert_not_called()
    mock_download.assert_not_called()

