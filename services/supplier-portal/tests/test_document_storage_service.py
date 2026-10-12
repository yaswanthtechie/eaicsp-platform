from datetime import timedelta
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.services.document_storage_service import (
    DocumentDownloadError,
    DocumentStorageError,
    DocumentStorageService,
    DocumentUploadError,
)


@pytest.fixture
def storage_service():
    """
    Create DocumentStorageService with a fake MinIO client.

    These are unit tests, so no real MinIO/Docker connection is used.
    """
    service = DocumentStorageService()

    fake_client = MagicMock()

    service.client = fake_client
    service.bucket_name = "supplier-documents"

    return service


@pytest.fixture
def pdf_upload_file():
    """
    Create an in-memory PDF upload with a real content-type header.
    """
    return UploadFile(
        filename="pan_card.pdf",
        file=BytesIO(b"%PDF-test-document%"),
        headers=Headers(
            {
                "content-type": "application/pdf",
            }
        ),
    )


@pytest.fixture
def generic_upload_file():
    """
    Create an upload without a content-type header.
    """
    return UploadFile(
        filename="document.bin",
        file=BytesIO(b"test-document%"),
        headers=Headers(),
    )


def make_s3_error(code: str) -> Exception:
    """
    Create an S3Error suitable for unit-test mocking.

    The installed MinIO version freezes S3Error attributes after
    construction, so the error code must be supplied directly to
    the constructor instead of being assigned afterward.
    """
    from minio.error import S3Error

    return S3Error(
        response=MagicMock(),
        code=code,
        message=f"Mocked {code} error",
        resource="test-resource",
        request_id="test-request-id",
        host_id="test-host-id",
    )


# ============================================================
# OBJECT KEY GENERATION
# ============================================================


def test_build_onboarding_object_key_uses_supplier_scope():
    object_key = DocumentStorageService.build_onboarding_object_key(
        supplier_id="SUP001",
        document_id="DOC001",
        file_name="pan_card.pdf",
    )

    assert object_key == (
        "suppliers/SUP001/onboarding/"
        "DOC001_pan_card.pdf"
    )


def test_build_onboarding_object_key_preserves_supplier_prefix():
    object_key = DocumentStorageService.build_onboarding_object_key(
        supplier_id="SUP002",
        document_id="DOC999",
        file_name="gst_certificate.pdf",
    )

    assert object_key.startswith(
        "suppliers/SUP002/onboarding/"
    )

    assert object_key.endswith(
        "DOC999_gst_certificate.pdf"
    )


def test_build_onboarding_object_key_strips_unix_directory_from_filename():
    object_key = DocumentStorageService.build_onboarding_object_key(
        supplier_id="SUP001",
        document_id="DOC001",
        file_name="../../secret/pan_card.pdf",
    )

    assert object_key == (
        "suppliers/SUP001/onboarding/"
        "DOC001_pan_card.pdf"
    )

    assert "../" not in object_key


def test_build_onboarding_object_key_strips_windows_directory_from_filename():
    object_key = DocumentStorageService.build_onboarding_object_key(
        supplier_id="SUP001",
        document_id="DOC001",
        file_name=r"C:\temp\pan_card.pdf",
    )

    assert object_key.endswith(
        "DOC001_pan_card.pdf"
    )

    assert r"C:\temp" not in object_key


def test_build_onboarding_object_key_uses_document_id_to_avoid_collision():
    first_key = DocumentStorageService.build_onboarding_object_key(
        supplier_id="SUP001",
        document_id="DOC001",
        file_name="document.pdf",
    )

    second_key = DocumentStorageService.build_onboarding_object_key(
        supplier_id="SUP001",
        document_id="DOC002",
        file_name="document.pdf",
    )

    assert first_key != second_key


def test_different_suppliers_get_different_object_prefixes():
    supplier_a_key = DocumentStorageService.build_onboarding_object_key(
        supplier_id="SUP001",
        document_id="DOC001",
        file_name="document.pdf",
    )

    supplier_b_key = DocumentStorageService.build_onboarding_object_key(
        supplier_id="SUP002",
        document_id="DOC001",
        file_name="document.pdf",
    )

    assert supplier_a_key != supplier_b_key

    assert supplier_a_key.startswith(
        "suppliers/SUP001/"
    )

    assert supplier_b_key.startswith(
        "suppliers/SUP002/"
    )


# ============================================================
# BUCKET INITIALIZATION
# ============================================================


def test_ensure_bucket_does_not_create_bucket_when_it_exists(
    storage_service,
):
    storage_service.client.bucket_exists.return_value = True

    storage_service.ensure_bucket()

    storage_service.client.bucket_exists.assert_called_once_with(
        "supplier-documents"
    )

    storage_service.client.make_bucket.assert_not_called()


def test_ensure_bucket_creates_bucket_when_missing(
    storage_service,
):
    storage_service.client.bucket_exists.return_value = False

    storage_service.ensure_bucket()

    storage_service.client.bucket_exists.assert_called_once_with(
        "supplier-documents"
    )

    storage_service.client.make_bucket.assert_called_once_with(
        "supplier-documents"
    )


def test_ensure_bucket_raises_storage_error_on_minio_failure(
    storage_service,
):
    storage_service.client.bucket_exists.side_effect = (
        make_s3_error("AccessDenied")
    )

    with pytest.raises(DocumentStorageError):
        storage_service.ensure_bucket()


# ============================================================
# ONBOARDING DOCUMENT UPLOAD
# ============================================================


def test_upload_onboarding_document_returns_object_key(
    storage_service,
    pdf_upload_file,
):
    storage_service.client.bucket_exists.return_value = True

    object_key = storage_service.upload_onboarding_document(
        supplier_id="SUP001",
        document_id="DOC001",
        file=pdf_upload_file,
    )

    assert object_key == (
        "suppliers/SUP001/onboarding/"
        "DOC001_pan_card.pdf"
    )


def test_upload_onboarding_document_creates_bucket_if_needed(
    storage_service,
    pdf_upload_file,
):
    storage_service.client.bucket_exists.return_value = False

    storage_service.upload_onboarding_document(
        supplier_id="SUP001",
        document_id="DOC001",
        file=pdf_upload_file,
    )

    storage_service.client.make_bucket.assert_called_once_with(
        "supplier-documents"
    )


def test_upload_onboarding_document_calls_minio_put_object(
    storage_service,
    pdf_upload_file,
):
    storage_service.client.bucket_exists.return_value = True

    object_key = storage_service.upload_onboarding_document(
        supplier_id="SUP001",
        document_id="DOC001",
        file=pdf_upload_file,
    )

    storage_service.client.put_object.assert_called_once()

    call_kwargs = (
        storage_service.client.put_object.call_args.kwargs
    )

    assert call_kwargs["bucket_name"] == "supplier-documents"
    assert call_kwargs["object_name"] == object_key
    assert call_kwargs["length"] == -1
    assert call_kwargs["part_size"] == 10 * 1024 * 1024
    assert call_kwargs["content_type"] == "application/pdf"


def test_upload_onboarding_document_uses_default_content_type(
    storage_service,
    generic_upload_file,
):
    storage_service.client.bucket_exists.return_value = True

    storage_service.upload_onboarding_document(
        supplier_id="SUP001",
        document_id="DOC001",
        file=generic_upload_file,
    )

    storage_service.client.put_object.assert_called_once()

    call_kwargs = (
        storage_service.client.put_object.call_args.kwargs
    )

    assert (
        call_kwargs["content_type"]
        == "application/octet-stream"
    )


def test_upload_onboarding_document_resets_file_pointer(
    storage_service,
    pdf_upload_file,
):
    storage_service.client.bucket_exists.return_value = True

    pdf_upload_file.file.read(5)

    storage_service.upload_onboarding_document(
        supplier_id="SUP001",
        document_id="DOC001",
        file=pdf_upload_file,
    )

    assert pdf_upload_file.file.tell() == 0


def test_upload_onboarding_document_raises_upload_error_on_s3_failure(
    storage_service,
    pdf_upload_file,
):
    storage_service.client.bucket_exists.return_value = True

    storage_service.client.put_object.side_effect = (
        make_s3_error("AccessDenied")
    )

    with pytest.raises(DocumentUploadError):
        storage_service.upload_onboarding_document(
            supplier_id="SUP001",
            document_id="DOC001",
            file=pdf_upload_file,
        )


def test_upload_onboarding_document_raises_upload_error_on_os_error(
    storage_service,
    pdf_upload_file,
):
    storage_service.client.bucket_exists.return_value = True

    storage_service.client.put_object.side_effect = OSError(
        "Unable to read uploaded file"
    )

    with pytest.raises(DocumentUploadError):
        storage_service.upload_onboarding_document(
            supplier_id="SUP001",
            document_id="DOC001",
            file=pdf_upload_file,
        )


def test_upload_onboarding_document_raises_upload_error_on_value_error(
    storage_service,
    pdf_upload_file,
):
    storage_service.client.bucket_exists.return_value = True

    storage_service.client.put_object.side_effect = ValueError(
        "Invalid upload"
    )

    with pytest.raises(DocumentUploadError):
        storage_service.upload_onboarding_document(
            supplier_id="SUP001",
            document_id="DOC001",
            file=pdf_upload_file,
        )


# ============================================================
# PRESIGNED DOWNLOAD URL
# ============================================================


def test_generate_download_url_returns_presigned_url(
    storage_service,
):
    expected_url = (
        "http://localhost:9000/supplier-documents/"
        "suppliers/SUP001/onboarding/"
        "DOC001_pan_card.pdf"
        "?X-Amz-Signature=test"
    )

    storage_service.client.presigned_get_object.return_value = (
        expected_url
    )

    url = storage_service.generate_download_url(
        object_key=(
            "suppliers/SUP001/onboarding/"
            "DOC001_pan_card.pdf"
        )
    )

    assert url == expected_url


def test_generate_download_url_calls_minio_with_correct_object_key(
    storage_service,
):
    storage_service.client.presigned_get_object.return_value = (
        "http://example.com/presigned"
    )

    object_key = (
        "suppliers/SUP001/onboarding/"
        "DOC001_pan_card.pdf"
    )

    result = storage_service.generate_download_url(
        object_key=object_key,
    )

    assert result == "http://example.com/presigned"

    storage_service.client.presigned_get_object.assert_called_once()

    call_kwargs = (
        storage_service.client.presigned_get_object.call_args.kwargs
    )

    assert call_kwargs["bucket_name"] == "supplier-documents"
    assert call_kwargs["object_name"] == object_key


def test_generate_download_url_uses_configured_expiry(
    storage_service,
    monkeypatch,
):
    storage_service.client.presigned_get_object.return_value = (
        "http://example.com/presigned"
    )

    monkeypatch.setattr(
        "app.services.document_storage_service.settings."
        "MINIO_PRESIGNED_EXPIRY_SECONDS",
        300,
    )

    storage_service.generate_download_url(
        object_key=(
            "suppliers/SUP001/onboarding/"
            "DOC001_pan_card.pdf"
        ),
    )

    call_kwargs = (
        storage_service.client.presigned_get_object.call_args.kwargs
    )

    assert call_kwargs["expires"] == timedelta(seconds=300)


def test_generate_download_url_raises_download_error_on_s3_failure(
    storage_service,
):
    storage_service.client.presigned_get_object.side_effect = (
        make_s3_error("NoSuchKey")
    )

    with pytest.raises(DocumentDownloadError):
        storage_service.generate_download_url(
            object_key=(
                "suppliers/SUP001/onboarding/"
                "DOC001_pan_card.pdf"
            ),
        )


def test_generate_download_url_raises_download_error_on_value_error(
    storage_service,
):
    storage_service.client.presigned_get_object.side_effect = (
        ValueError("Invalid expiry")
    )

    with pytest.raises(DocumentDownloadError):
        storage_service.generate_download_url(
            object_key=(
                "suppliers/SUP001/onboarding/"
                "DOC001_pan_card.pdf"
            ),
        )


# ============================================================
# OBJECT EXISTENCE
# ============================================================


def test_object_exists_returns_true_when_object_exists(
    storage_service,
):
    storage_service.client.stat_object.return_value = (
        SimpleNamespace(
            object_name=(
                "suppliers/SUP001/onboarding/"
                "DOC001_pan_card.pdf"
            )
        )
    )

    result = storage_service.object_exists(
        object_key=(
            "suppliers/SUP001/onboarding/"
            "DOC001_pan_card.pdf"
        ),
    )

    assert result is True

    storage_service.client.stat_object.assert_called_once_with(
        bucket_name="supplier-documents",
        object_name=(
            "suppliers/SUP001/onboarding/"
            "DOC001_pan_card.pdf"
        ),
    )


@pytest.mark.parametrize(
    "error_code",
    [
        "NoSuchKey",
        "NoSuchObject",
        "NotFound",
    ],
)
def test_object_exists_returns_false_for_missing_object(
    storage_service,
    error_code,
):
    error = make_s3_error(error_code)

    storage_service.client.stat_object.side_effect = error

    result = storage_service.object_exists(
        object_key=(
            "suppliers/SUP001/onboarding/"
            "DOC001_pan_card.pdf"
        ),
    )

    assert result is False


def test_object_exists_raises_storage_error_for_unexpected_s3_failure(
    storage_service,
):
    error = make_s3_error("AccessDenied")

    storage_service.client.stat_object.side_effect = error

    with pytest.raises(DocumentStorageError):
        storage_service.object_exists(
            object_key=(
                "suppliers/SUP001/onboarding/"
                "DOC001_pan_card.pdf"
            ),
        )


def test_object_exists_raises_storage_error_for_unexpected_exception(
    storage_service,
):
    storage_service.client.stat_object.side_effect = RuntimeError(
        "Unexpected storage failure"
    )

    with pytest.raises(RuntimeError):
        storage_service.object_exists(
            object_key=(
                "suppliers/SUP001/onboarding/"
                "DOC001_pan_card.pdf"
            ),
        )