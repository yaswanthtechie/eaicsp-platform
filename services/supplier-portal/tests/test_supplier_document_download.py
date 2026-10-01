import io

import pytest
from fastapi.testclient import TestClient

from app.core.auth import verify_token
from app.core.config import settings
from app.main import app
from app.services.document_storage_service import DocumentDownloadError
from app.services.supplier_onboarding_service import (
    suppliers,
    supplier_documents,
    supplier_onboarding_history,
)


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
    "country": "India",
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
    "country": "India",
    "required_documents": [
        "gst_certificate",
        "pan_card",
        "bank_certificate",
    ],
}

# ============================================================
# HELPERS
# ============================================================


def register_supplier(procurement_client, registration):
    """Register a supplier so documents can be uploaded."""
    return procurement_client.post(
        "/api/v1/suppliers/register",
        json=registration,
    )


def upload_document(
    supplier_client,
    supplier_id,
    document_type="pan_card",
):
    """Upload one PDF document and return the API response."""
    return supplier_client.post(
        f"/api/v1/suppliers/{supplier_id}/documents",
        files={
            "file": (
                f"{document_type}.pdf",
                io.BytesIO(b"%PDF-1.4\nTest supplier document"),
                "application/pdf",
            )
        },
        data={
            "document_type": document_type,
        },
    )


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture(autouse=True)
def clean_onboarding_storage():
    """
    Reset supplier onboarding in-memory storage before and
    after every download test.
    """
    suppliers.clear()
    supplier_documents.clear()
    supplier_onboarding_history.clear()

    yield

    suppliers.clear()
    supplier_documents.clear()
    supplier_onboarding_history.clear()

@pytest.fixture
def supplier_a_document(procurement_client, supplier_client):
    """
    Register SUP001 and upload one document.

    Returns:
        Upload response JSON.
    """
    registration_response = register_supplier(
        procurement_client,
        SUPPLIER_A_REGISTRATION,
    )

    assert registration_response.status_code in (200, 201), (
        "Supplier registration failed: "
        f"{registration_response.status_code} "
        f"{registration_response.text}"
    )

    upload_response = upload_document(
        supplier_client,
        "SUP001",
        "pan_card",
    )

    assert upload_response.status_code == 201, (
        "Document upload failed: "
        f"{upload_response.status_code} "
        f"{upload_response.text}"
    )

    return upload_response.json()


@pytest.fixture
def supplier_b_document(procurement_client, supplier_b_client):
    """
    Register SUP002 and upload one document.

    Returns:
        Upload response JSON.
    """
    registration_response = register_supplier(
        procurement_client,
        SUPPLIER_B_REGISTRATION,
    )

    assert registration_response.status_code in (200, 201), (
        "Supplier registration failed: "
        f"{registration_response.status_code} "
        f"{registration_response.text}"
    )

    upload_response = upload_document(
        supplier_b_client,
        "SUP002",
        "pan_card",
    )

    assert upload_response.status_code == 201, (
        "Document upload failed: "
        f"{upload_response.status_code} "
        f"{upload_response.text}"
    )

    return upload_response.json()


# ============================================================
# 1. SUCCESSFUL DOWNLOAD
# ============================================================


def test_supplier_can_download_own_document(
    supplier_client,
    supplier_a_document,
    monkeypatch,
):
    """
    Supplier can download its own document.

    Expected:
        200
        Valid presigned URL
    """
    document_id = supplier_a_document["document_id"]

    expected_url = (
        "https://minio.test/presigned/"
        f"{document_id}"
    )

    monkeypatch.setattr(
        "app.routes.supplier_onboarding."
        "document_storage_service.generate_download_url",
        lambda *, object_key: expected_url,
    )

    response = supplier_client.get(
        f"/api/v1/suppliers/SUP001/"
        f"documents/{document_id}/download"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["document_id"] == document_id
    assert body["supplier_id"] == "SUP001"
    assert body["file_name"] == supplier_a_document["file_name"]
    assert body["download_url"] == expected_url
    assert (
        body["expires_in_seconds"]
        == settings.MINIO_PRESIGNED_EXPIRY_SECONDS
    )


# ============================================================
# 2. RESPONSE CONTRACT
# ============================================================


def test_download_response_contains_exact_contract(
    supplier_client,
    supplier_a_document,
    monkeypatch,
):
    """
    Verify the download response contains exactly the fields
    defined by SupplierDocumentDownloadResponse.
    """
    document_id = supplier_a_document["document_id"]

    monkeypatch.setattr(
        "app.routes.supplier_onboarding."
        "document_storage_service.generate_download_url",
        lambda *, object_key: "https://minio.test/download",
    )

    response = supplier_client.get(
        f"/api/v1/suppliers/SUP001/"
        f"documents/{document_id}/download"
    )

    assert response.status_code == 200

    body = response.json()

    assert set(body.keys()) == {
        "document_id",
        "supplier_id",
        "file_name",
        "download_url",
        "expires_in_seconds",
    }


# ============================================================
# 3. CORRECT OBJECT KEY
# ============================================================


def test_download_uses_document_path_as_object_key(
    supplier_client,
    supplier_a_document,
    monkeypatch,
):
    """
    The storage service must receive document["document_path"]
    as object_key.
    """
    document_id = supplier_a_document["document_id"]

    captured = {}

    def fake_generate_download_url(*, object_key):
        captured["object_key"] = object_key
        return "https://minio.test/download"

    monkeypatch.setattr(
        "app.routes.supplier_onboarding."
        "document_storage_service.generate_download_url",
        fake_generate_download_url,
    )

    response = supplier_client.get(
        f"/api/v1/suppliers/SUP001/"
        f"documents/{document_id}/download"
    )

    assert response.status_code == 200

    expected_object_key = supplier_a_document["document_path"]

    assert captured["object_key"] == expected_object_key


# ============================================================
# 4. CROSS-SUPPLIER URL ACCESS
# ============================================================


def test_supplier_cannot_download_another_supplier_document(
    supplier_client,
    supplier_b_document,
    monkeypatch,
):
    """
    SUP001 must not be able to access SUP002's document
    through the SUP002 supplier URL.

    Expected:
        403
        Storage must not be called.
    """
    document_id = supplier_b_document["document_id"]

    storage_called = False

    def fake_generate_download_url(*, object_key):
        nonlocal storage_called
        storage_called = True
        return "https://minio.test/should-not-be-called"

    monkeypatch.setattr(
        "app.routes.supplier_onboarding."
        "document_storage_service.generate_download_url",
        fake_generate_download_url,
    )

    response = supplier_client.get(
        f"/api/v1/suppliers/SUP002/"
        f"documents/{document_id}/download"
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Supplier access is restricted to own data"
    )

    assert storage_called is False


# ============================================================
# 5. CROSS-SUPPLIER INFORMATION LEAK PREVENTION
# ============================================================


def test_supplier_cannot_download_other_supplier_document_id(
    supplier_client,
    supplier_b_document,
    monkeypatch,
):
    """
    A SUP002 document ID supplied under the SUP001 URL must
    not expose the SUP002 document.

    Expected:
        404
        Storage must not be called.
    """
    document_id = supplier_b_document["document_id"]

    storage_called = False

    def fake_generate_download_url(*, object_key):
        nonlocal storage_called
        storage_called = True
        return "https://minio.test/should-not-be-called"

    monkeypatch.setattr(
        "app.routes.supplier_onboarding."
        "document_storage_service.generate_download_url",
        fake_generate_download_url,
    )

    response = supplier_client.get(
        f"/api/v1/suppliers/SUP001/"
        f"documents/{document_id}/download"
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Supplier document not found."
    )

    assert storage_called is False


# ============================================================
# 6. UNKNOWN DOCUMENT
# ============================================================


def test_download_unknown_document_returns_404(
    supplier_client,
    supplier_a_document,
    monkeypatch,
):
    """
    Valid supplier + non-existent document ID -> 404.
    """
    storage_called = False

    def fake_generate_download_url(*, object_key):
        nonlocal storage_called
        storage_called = True
        return "https://minio.test/should-not-be-called"

    monkeypatch.setattr(
        "app.routes.supplier_onboarding."
        "document_storage_service.generate_download_url",
        fake_generate_download_url,
    )

    response = supplier_client.get(
        "/api/v1/suppliers/SUP001/"
        "documents/DOC-DOES-NOT-EXIST/download"
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Supplier document not found."
    )

    assert storage_called is False


# ============================================================
# 7. UNKNOWN SUPPLIER
# ============================================================


def test_download_document_for_unknown_supplier_returns_404(
    procurement_client,
    monkeypatch,
):
    """
    Unknown supplier should return 404 before attempting
    document download.
    """
    storage_called = False

    def fake_generate_download_url(*, object_key):
        nonlocal storage_called
        storage_called = True
        return "https://minio.test/should-not-be-called"

    monkeypatch.setattr(
        "app.routes.supplier_onboarding."
        "document_storage_service.generate_download_url",
        fake_generate_download_url,
    )

    response = procurement_client.get(
        "/api/v1/suppliers/SUP999/"
        "documents/DOC-UNKNOWN/download"
    )

    assert response.status_code == 404

    assert storage_called is False


# ============================================================
# 8. SUPPLIER WITHOUT supplier_id
# ============================================================


def test_supplier_without_supplier_id_cannot_download_document(
    supplier_no_id_client,
    monkeypatch,
):
    """
    Supplier user without resolved supplier_id must be rejected.
    """
    storage_called = False

    def fake_generate_download_url(*, object_key):
        nonlocal storage_called
        storage_called = True
        return "https://minio.test/should-not-be-called"

    monkeypatch.setattr(
        "app.routes.supplier_onboarding."
        "document_storage_service.generate_download_url",
        fake_generate_download_url,
    )

    response = supplier_no_id_client.get(
        "/api/v1/suppliers/SUP001/"
        "documents/DOC-ANY/download"
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Supplier identity could not be resolved"
    )

    assert storage_called is False


# ============================================================
# 9. STORAGE DOWNLOAD FAILURE
# ============================================================


def test_download_returns_502_when_storage_fails(
    supplier_client,
    supplier_a_document,
    monkeypatch,
):
    """
    Storage service failure must be translated into HTTP 502.
    """
    document_id = supplier_a_document["document_id"]

    def fake_generate_download_url(*, object_key):
        raise DocumentDownloadError(
            "Unable to generate download URL."
        )

    monkeypatch.setattr(
        "app.routes.supplier_onboarding."
        "document_storage_service.generate_download_url",
        fake_generate_download_url,
    )

    response = supplier_client.get(
        f"/api/v1/suppliers/SUP001/"
        f"documents/{document_id}/download"
    )

    assert response.status_code == 502

    assert response.json()["detail"] == (
        "Unable to generate download URL."
    )


# ============================================================
# 10. PROCUREMENT MANAGER ACCESS
# ============================================================


def test_procurement_manager_can_download_supplier_document(
    procurement_client,
    supplier_a_document,
    monkeypatch,
):
    """
    Procurement manager is an authorized non-supplier role and
    can download a supplier document.
    """
    document_id = supplier_a_document["document_id"]

    expected_url = (
        "https://minio.test/procurement-download"
    )

    monkeypatch.setattr(
        "app.routes.supplier_onboarding."
        "document_storage_service.generate_download_url",
        lambda *, object_key: expected_url,
    )

    response = procurement_client.get(
        f"/api/v1/suppliers/SUP001/"
        f"documents/{document_id}/download"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["document_id"] == document_id
    assert body["supplier_id"] == "SUP001"
    assert body["download_url"] == expected_url


# ============================================================
# 11. NO AUTHENTICATION
# ============================================================


def test_download_requires_authentication(
    supplier_a_document,
    monkeypatch,
):
    """
    No authentication token -> 401.

    A plain TestClient is intentionally used because the
    authenticated supplier_client installs a dependency override.
    """
    document_id = supplier_a_document["document_id"]

    # Remove the test authentication override so the real
    # authentication dependency executes.
    app.dependency_overrides.pop(verify_token, None)

    try:
        monkeypatch.setattr(
            "app.routes.supplier_onboarding."
            "document_storage_service.generate_download_url",
            lambda *, object_key: (
                "https://minio.test/should-not-be-called"
            ),
        )

        with TestClient(app) as unauthenticated_client:
            response = unauthenticated_client.get(
                f"/api/v1/suppliers/SUP001/"
                f"documents/{document_id}/download"
            )

        assert response.status_code == 401

    finally:
        # Restore the normal test authentication override.
        from conftest import SUPPLIER_USER

        app.dependency_overrides[verify_token] = (
            lambda: SUPPLIER_USER
        )

