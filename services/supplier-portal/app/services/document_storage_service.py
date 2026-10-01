from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi import UploadFile
from minio import Minio
from minio.error import S3Error

from app.core.config import settings


class DocumentStorageError(Exception):
    """Base exception for document storage failures."""


class DocumentUploadError(DocumentStorageError):
    """Raised when a document cannot be uploaded."""


class DocumentDownloadError(DocumentStorageError):
    """Raised when a document download URL cannot be generated."""


class DocumentStorageService:
    """
    MinIO-backed storage service for supplier documents.

    Supplier documents are stored under supplier-specific
    object prefixes.

    Example:

        suppliers/SUP001/onboarding/<document_id>_pan_card.pdf

    The object key is stored by the application.
    Temporary presigned URLs are generated only when a
    download is explicitly requested.
    """

    def __init__(self) -> None:
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )

        self.bucket_name = settings.MINIO_BUCKET

    # ============================================================
    # BUCKET INITIALIZATION
    # ============================================================

    def ensure_bucket(self) -> None:
        """
        Ensure the configured MinIO bucket exists.
        """
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)

        except S3Error as exc:
            raise DocumentStorageError(
                f"Unable to initialize MinIO bucket "
                f"'{self.bucket_name}'."
            ) from exc

    # ============================================================
    # OBJECT KEY
    # ============================================================

    @staticmethod
    def build_onboarding_object_key(
        supplier_id: str,
        document_id: str,
        file_name: str,
    ) -> str:
        """
        Build a supplier-scoped object key.

        Example:

            suppliers/SUP001/onboarding/
            <document_id>_pan_card.pdf
        """

        safe_file_name = Path(
            file_name
        ).name

        return (
            f"suppliers/{supplier_id}/"
            f"onboarding/{document_id}_{safe_file_name}"
        )

    @staticmethod
    def build_invoice_object_key(
        supplier_id: str,
        invoice_number: str,
        file_name: str,
    ) -> str:
        """
        Build a supplier-scoped MinIO object key for an invoice PDF.

        Example:
            suppliers/SUP001/invoices/INV1001.pdf

        The uploaded filename is intentionally not used as the
        object filename. One invoice has one canonical PDF object.
        """

        safe_invoice_number = Path(
            invoice_number
        ).name

        return (
            f"suppliers/{supplier_id}/"
            f"invoices/{safe_invoice_number}.pdf"
        )

    # ============================================================
    # UPLOAD ONBOARDING DOCUMENT
    # ============================================================

    def upload_onboarding_document(
        self,
        *,
        supplier_id: str,
        document_id: str,
        file: UploadFile,
    ) -> str:
        """
        Upload an onboarding document to MinIO.

        Returns:
            MinIO object key.

        The returned object key is stored with the document
        metadata. A public or presigned URL is never stored.
        """

        object_key = self.build_onboarding_object_key(
            supplier_id=supplier_id,
            document_id=document_id,
            file_name=file.filename or "document",
        )

        try:
            self.ensure_bucket()

            # The caller may have read the file while validating
            # its size. Start from the beginning before uploading.
            file.file.seek(0)

            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_key,
                data=file.file,
                length=-1,
                part_size=10 * 1024 * 1024,
                content_type=(
                    file.content_type
                    or "application/octet-stream"
                ),
            )

            return object_key

        except (S3Error, OSError, ValueError) as exc:
            raise DocumentUploadError(
                f"Unable to upload document for "
                f"supplier '{supplier_id}'."
            ) from exc

    def upload_invoice_document(
        self,
        *,
        supplier_id: str,
        invoice_number: str,
        file: UploadFile,
    ) -> str:
        """
        Upload an invoice PDF to MinIO.

        Returns:
            MinIO object key.

        Example:
            suppliers/SUP001/invoices/INV1001.pdf
        """

        object_key = self.build_invoice_object_key(
            supplier_id=supplier_id,
            invoice_number=invoice_number,
            file_name=file.filename or "invoice.pdf",
        )

        try:
            self.ensure_bucket()

            # The invoice service may already have read the file
            # while validating its size/signature.
            file.file.seek(0)

            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_key,
                data=file.file,
                length=-1,
                part_size=10 * 1024 * 1024,
                content_type="application/pdf",
            )

            return object_key

        except (S3Error, OSError, ValueError) as exc:
            raise DocumentUploadError(
                f"Unable to upload invoice document "
                f"for supplier '{supplier_id}'."
            ) from exc

    # ============================================================
    # PRESIGNED DOWNLOAD URL
    # ============================================================

    def generate_download_url(
        self,
        *,
        object_key: str,
    ) -> str:
        """
        Generate a short-lived presigned download URL.

        IMPORTANT:
        Supplier authorization must happen before calling this
        method. This service only handles storage operations.
        """

        try:
            expiry_seconds = (
                settings.MINIO_PRESIGNED_EXPIRY_SECONDS
            )

            return self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_key,
                expires=timedelta(
                    seconds=expiry_seconds
                ),
            )

        except (S3Error, ValueError) as exc:
            raise DocumentDownloadError(
                "Unable to generate document "
                "download URL."
            ) from exc

    # ============================================================
    # OBJECT EXISTENCE
    # ============================================================

    def object_exists(
        self,
        *,
        object_key: str,
    ) -> bool:
        """
        Check whether an object exists in MinIO.

        Mainly useful for integration tests and operational
        verification.
        """

        try:
            self.client.stat_object(
                bucket_name=self.bucket_name,
                object_name=object_key,
            )

            return True

        except S3Error as exc:
            if exc.code in {
                "NoSuchKey",
                "NoSuchObject",
                "NotFound",
            }:
                return False

            raise DocumentStorageError(
                "Unable to check document existence "
                "in MinIO."
            ) from exc

    def delete_object(
        self,
        *,
        object_key: str,
    ) -> None:
        """
        Delete a document object from MinIO.
        """

        try:
            self.client.remove_object(
                bucket_name=self.bucket_name,
                object_name=object_key,
            )

        except S3Error as exc:
            raise DocumentStorageError(
                "Unable to delete document from MinIO."
            ) from exc
    def list_objects(
        self,
        *,
        prefix: str,
    ):
        """
        List objects from MinIO under the supplied prefix.

        Used by invoice orphan-file detection.
        """

        try:
            self.ensure_bucket()

            return list(
                self.client.list_objects(
                    bucket_name=self.bucket_name,
                    prefix=prefix,
                    recursive=True,
                )
            )

        except S3Error as exc:
            raise DocumentStorageError(
                "Unable to list documents in MinIO."
            ) from exc

document_storage_service = DocumentStorageService()

