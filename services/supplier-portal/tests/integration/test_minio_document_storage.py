"""
Integration tests for the real MinIO-backed document storage service.

These tests require a running Docker MinIO instance.

Run with:

    python -m pytest tests/integration/test_minio_document_storage.py -v -m integration
"""

from __future__ import annotations

import io
import os
import urllib.request
import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from dotenv import dotenv_values
from fastapi import UploadFile
from minio import Minio

from app.core.config import settings
from app.services.document_storage_service import DocumentStorageService


pytestmark = pytest.mark.integration


def _load_real_minio_credentials() -> tuple[str, str]:
    """
    Load the real MinIO credentials from the process environment
    or the project's .env file.

    tests/conftest.py intentionally installs dummy credentials before
    importing the application, so integration tests must explicitly
    obtain the real credentials.
    """
    env_values = dotenv_values(".env")

    access_key = (
        os.environ.get("REAL_MINIO_ACCESS_KEY")
        or env_values.get("MINIO_ACCESS_KEY")
    )

    secret_key = (
        os.environ.get("REAL_MINIO_SECRET_KEY")
        or env_values.get("MINIO_SECRET_KEY")
    )

    if not access_key:
        raise RuntimeError(
            "Real MINIO_ACCESS_KEY was not found. "
            "Set it in services/supplier-portal/.env."
        )

    if not secret_key:
        raise RuntimeError(
            "Real MINIO_SECRET_KEY was not found. "
            "Set it in services/supplier-portal/.env."
        )

    return str(access_key), str(secret_key)


@pytest.fixture(scope="module")
def storage_service():
    """
    Use the real MinIO-backed storage service.

    Unit-test FakeMinioClient state is deliberately bypassed here.
    """
    access_key, secret_key = _load_real_minio_credentials()

    real_client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=access_key,
        secret_key=secret_key,
        secure=settings.MINIO_SECURE,
    )

    service = DocumentStorageService()

    # Replace only this integration-test service's client.
    service.client = real_client

    try:
        service.ensure_bucket()
    except Exception as exc:
        pytest.fail(
            "Real MinIO integration setup failed.\n"
            f"Endpoint: {settings.MINIO_ENDPOINT}\n"
            f"Bucket: {settings.MINIO_BUCKET}\n"
            "Verify that Docker MinIO is running and that "
            "MINIO_ACCESS_KEY / MINIO_SECRET_KEY in .env "
            "match the MinIO container credentials.\n"
            f"Original error: {exc}"
        )

    return service


@pytest.fixture
def unique_document():
    """
    Generate unique supplier/document identifiers so repeated
    integration-test runs cannot collide.
    """
    supplier_id = (
        f"INTEGRATION-{uuid.uuid4().hex[:8].upper()}"
    )
    document_id = str(uuid.uuid4())

    return supplier_id, document_id


@pytest.fixture
def cleanup_objects(storage_service):
    """
    Track objects created by each test and remove them afterwards.
    """
    object_keys: list[str] = []

    yield object_keys

    for object_key in object_keys:
        try:
            storage_service.client.remove_object(
                bucket_name=storage_service.bucket_name,
                object_name=object_key,
            )
        except Exception:
            # Cleanup must never hide the original test failure.
            pass


def create_upload_file(
    *,
    filename: str = "pan_card.pdf",
    content: bytes = b"%PDF-1.4\nIntegration test document",
    content_type: str = "application/pdf",
) -> UploadFile:
    """
    Create a FastAPI UploadFile backed by an in-memory stream.
    """
    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers={
            "content-type": content_type,
        },
    )


def test_real_minio_upload_creates_supplier_scoped_object(
    storage_service,
    unique_document,
    cleanup_objects,
):
    """
    Upload a document to real MinIO and verify the supplier-scoped
    object key.
    """
    supplier_id, document_id = unique_document

    file = create_upload_file()

    object_key = storage_service.upload_onboarding_document(
        supplier_id=supplier_id,
        document_id=document_id,
        file=file,
    )

    cleanup_objects.append(object_key)

    assert object_key.startswith(
        f"suppliers/{supplier_id}/onboarding/"
    )

    assert object_key.endswith(
        f"_{file.filename}"
    )

    assert supplier_id in object_key
    assert document_id in object_key


def test_real_minio_upload_object_exists(
    storage_service,
    unique_document,
    cleanup_objects,
):
    """
    Verify that an uploaded object exists in real MinIO.
    """
    supplier_id, document_id = unique_document

    file = create_upload_file(
        filename="gst_certificate.pdf",
    )

    object_key = storage_service.upload_onboarding_document(
        supplier_id=supplier_id,
        document_id=document_id,
        file=file,
    )

    cleanup_objects.append(object_key)

    assert (
        storage_service.object_exists(
            object_key=object_key,
        )
        is True
    )


def test_real_minio_upload_preserves_uploaded_content(
    storage_service,
    unique_document,
    cleanup_objects,
):
    """
    Verify that uploaded content can be read back unchanged.
    """
    supplier_id, document_id = unique_document

    content = (
        b"%PDF-1.4\n"
        b"Real MinIO integration test content\n"
    )

    file = create_upload_file(
        filename="bank_certificate.pdf",
        content=content,
    )

    object_key = storage_service.upload_onboarding_document(
        supplier_id=supplier_id,
        document_id=document_id,
        file=file,
    )

    cleanup_objects.append(object_key)

    response = storage_service.client.get_object(
        bucket_name=storage_service.bucket_name,
        object_name=object_key,
    )

    try:
        downloaded_content = response.read()
    finally:
        response.close()
        response.release_conn()

    assert downloaded_content == content


def test_real_minio_different_suppliers_have_different_object_keys(
    storage_service,
):
    """
    Verify supplier-specific object key isolation.
    """
    document_id_a = str(uuid.uuid4())
    document_id_b = str(uuid.uuid4())

    object_key_a = (
        storage_service.build_onboarding_object_key(
            supplier_id="SUP001",
            document_id=document_id_a,
            file_name="pan_card.pdf",
        )
    )

    object_key_b = (
        storage_service.build_onboarding_object_key(
            supplier_id="SUP002",
            document_id=document_id_b,
            file_name="pan_card.pdf",
        )
    )

    assert object_key_a != object_key_b

    assert object_key_a.startswith(
        "suppliers/SUP001/onboarding/"
    )

    assert object_key_b.startswith(
        "suppliers/SUP002/onboarding/"
    )


def test_real_minio_supplier_a_object_is_not_supplier_b_object(
    storage_service,
):
    """
    Verify that Supplier A and Supplier B have distinct
    supplier-scoped object keys.
    """
    document_id_a = str(uuid.uuid4())
    document_id_b = str(uuid.uuid4())

    object_key_a = (
        storage_service.build_onboarding_object_key(
            supplier_id="SUP001",
            document_id=document_id_a,
            file_name="pan_card.pdf",
        )
    )

    object_key_b = (
        storage_service.build_onboarding_object_key(
            supplier_id="SUP002",
            document_id=document_id_b,
            file_name="pan_card.pdf",
        )
    )

    assert object_key_a != object_key_b

    assert "/SUP001/" in object_key_a
    assert "/SUP002/" in object_key_b

    assert (
        storage_service.object_exists(
            object_key=object_key_a,
        )
        is False
    )

    assert (
        storage_service.object_exists(
            object_key=object_key_b,
        )
        is False
    )


def test_real_minio_presigned_url_is_generated(
    storage_service,
    unique_document,
    cleanup_objects,
):
    """
    Verify that real MinIO generates a presigned download URL.
    """
    supplier_id, document_id = unique_document

    file = create_upload_file()

    object_key = storage_service.upload_onboarding_document(
        supplier_id=supplier_id,
        document_id=document_id,
        file=file,
    )

    cleanup_objects.append(object_key)

    url = storage_service.generate_download_url(
        object_key=object_key,
    )

    assert isinstance(url, str)
    assert url.startswith(
        ("http://", "https://")
    )

    parsed = urlparse(url)

    assert parsed.scheme in {"http", "https"}
    assert parsed.netloc
    assert parsed.path.endswith(
        f"/{object_key}"
    )


def test_real_minio_presigned_url_contains_configured_expiry(
    storage_service,
    unique_document,
    cleanup_objects,
):
    """
    Verify the configured short-lived presigned URL expiry.
    """
    supplier_id, document_id = unique_document

    file = create_upload_file()

    object_key = storage_service.upload_onboarding_document(
        supplier_id=supplier_id,
        document_id=document_id,
        file=file,
    )

    cleanup_objects.append(object_key)

    url = storage_service.generate_download_url(
        object_key=object_key,
    )

    query = parse_qs(
        urlparse(url).query
    )

    assert "X-Amz-Expires" in query

    expires = int(
        query["X-Amz-Expires"][0]
    )

    assert (
        expires
        == settings.MINIO_PRESIGNED_EXPIRY_SECONDS
    )

    assert expires <= 300


def test_real_minio_presigned_url_can_download_object(
    storage_service,
    unique_document,
    cleanup_objects,
):
    """
    Verify that the real presigned URL can download the object.
    """
    supplier_id, document_id = unique_document

    content = (
        b"%PDF-1.4\n"
        b"Presigned URL integration test\n"
    )

    file = create_upload_file(
        filename="pan_card.pdf",
        content=content,
    )

    object_key = storage_service.upload_onboarding_document(
        supplier_id=supplier_id,
        document_id=document_id,
        file=file,
    )

    cleanup_objects.append(object_key)

    url = storage_service.generate_download_url(
        object_key=object_key,
    )

    with urllib.request.urlopen(
        url,
        timeout=10,
    ) as response:
        downloaded_content = response.read()

    assert downloaded_content == content


def test_real_minio_missing_object_returns_false(
    storage_service,
):
    """
    A missing object must return False.
    """
    missing_object_key = (
        "suppliers/integration-test/"
        f"missing-{uuid.uuid4()}.pdf"
    )

    assert (
        storage_service.object_exists(
            object_key=missing_object_key,
        )
        is False
    )


def test_real_minio_object_is_removed_after_cleanup(
    storage_service,
    unique_document,
):
    """
    Verify real MinIO object deletion.
    """
    supplier_id, document_id = unique_document

    file = create_upload_file()

    object_key = storage_service.upload_onboarding_document(
        supplier_id=supplier_id,
        document_id=document_id,
        file=file,
    )

    assert (
        storage_service.object_exists(
            object_key=object_key,
        )
        is True
    )

    storage_service.client.remove_object(
        bucket_name=storage_service.bucket_name,
        object_name=object_key,
    )

    assert (
        storage_service.object_exists(
            object_key=object_key,
        )
        is False
    )