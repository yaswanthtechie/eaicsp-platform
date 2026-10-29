import os
from datetime import datetime, timezone
from types import SimpleNamespace

# Dummy MinIO credentials for normal tests only.
#
# These must be defined before importing app because
# app.core.config creates Settings() at import time.
os.environ.setdefault(
    "MINIO_ACCESS_KEY",
    "test-access-key",
)
os.environ.setdefault(
    "MINIO_SECRET_KEY",
    "test-secret-key",
)

# Unit tests never connect; DB tests build their own SQLite engine.
os.environ.setdefault(
    "DATABASE_URL",
    "sqlite://",
)
# Unit tests must not start the R15 Kafka consumer or outbox publisher.
os.environ.setdefault("PO_KAFKA_ENABLED", "false")
os.environ.setdefault("PO_OUTBOX_ENABLED", "false")
os.environ.setdefault("SHIPMENT_OUTBOX_ENABLED", "false")
os.environ.setdefault("ETA_KAFKA_ENABLED", "false")
os.environ.setdefault("GOODS_RECEIVED_KAFKA_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient
from minio.error import S3Error

from app.main import app
from app.core.auth import verify_token
from app.services.document_storage_service import (
    document_storage_service,
)

from app.services.supplier_compliance_service import (
    supplier_compliance_service,
)
from app.models.shipment import Shipment

class FakeMinioClient:
    """
    In-memory MinIO replacement used by non-integration tests.

    This prevents unit/API tests from requiring a running
    MinIO Docker container.

    Integration tests marked with @pytest.mark.integration
    continue to use the real MinIO client.
    """

    def __init__(self):
        self.buckets = set()
        self.objects = {}

    def bucket_exists(self, bucket_name):
        return bucket_name in self.buckets

    def make_bucket(self, bucket_name):
        self.buckets.add(bucket_name)

    def put_object(
        self,
        bucket_name,
        object_name,
        data,
        length=-1,
        part_size=0,
        content_type=None,
    ):
        content = data.read()

        self.objects[
            (bucket_name, object_name)
        ] = SimpleNamespace(
            object_name=object_name,
            content=content,
            content_type=content_type,
            last_modified=datetime.now(timezone.utc),
            size=len(content),
        )

    def _missing(self, bucket_name, object_name):
        return S3Error(
            code="NoSuchKey",
            message="Object does not exist",
            resource=f"/{bucket_name}/{object_name}",
            request_id="fake",
            host_id="fake",
            response=None,
            bucket_name=bucket_name,
            object_name=object_name,
        )

    def stat_object(self, bucket_name, object_name):
        obj = self.objects.get(
            (bucket_name, object_name)
        )

        if obj is None:
            raise self._missing(
                bucket_name,
                object_name,
            )

        return obj

    def remove_object(
        self,
        bucket_name,
        object_name,
    ):
        self.objects.pop(
            (bucket_name, object_name),
            None,
        )

    def list_objects(
        self,
        bucket_name,
        prefix="",
        recursive=True,
    ):
        return [
            obj
            for (bucket, key), obj in self.objects.items()
            if bucket == bucket_name
            and key.startswith(prefix)
        ]

    def presigned_get_object(
        self,
        bucket_name,
        object_name,
        expires,
    ):
        return (
            f"http://minio.test/{bucket_name}/{object_name}"
            f"?X-Amz-Expires="
            f"{int(expires.total_seconds())}"
        )


@pytest.fixture(autouse=True)
def fake_minio(request, monkeypatch):
    """
    Replace the real MinIO client for all non-integration tests.

    Integration tests use the real MinIO Docker container.
    """

    if request.node.get_closest_marker("integration"):
        yield None
        return

    fake = FakeMinioClient()

    monkeypatch.setattr(
        document_storage_service,
        "client",
        fake,
    )

    yield fake


SUPPLIER_USER = {
    "valid": True,
    "user_id": 8,
    "email": "supplier@company.com",
    "full_name": "Supplier User",
    "role": "supplier",
    "supplier_id": "SUP-00001",
    "is_active": True,
}


SUPPLIER_B_USER = {
    "valid": True,
    "user_id": 99,
    "role": "supplier",
    "supplier_id": "SUP-00002",
    "email": "supplierb@example.com",
    "full_name": "Supplier B",
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


COMPLIANCE_USER = {
    "valid": True,
    "user_id": 6,
    "email": "compliance@company.com",
    "full_name": "Compliance Officer",
    "role": "compliance_officer",
    "supplier_id": None,
    "is_active": True,
}


class AuthenticatedTestClient(TestClient):
    """
    TestClient that applies its own authentication user
    immediately before every request.

    This prevents different role-specific clients from
    overwriting each other's authentication state.
    """

    def __init__(self, app, user):
        self.test_user = user
        super().__init__(app)

    def request(self, *args, **kwargs):
        async def mock_verify_token():
            return self.test_user

        app.dependency_overrides[verify_token] = (
            mock_verify_token
        )

        return super().request(*args, **kwargs)


@pytest.fixture(autouse=True)
def mock_authentication():
    """
    Default authentication for tests that do not explicitly
    request a role-specific client.

    Default user = SUP-00001 supplier.
    """

    async def mock_verify_token():
        return SUPPLIER_USER

    app.dependency_overrides[verify_token] = (
        mock_verify_token
    )

    yield

    app.dependency_overrides.pop(
        verify_token,
        None,
    )


@pytest.fixture
def supplier_client():
    """
    TestClient authenticated as supplier SUP-00001.
    """

    with AuthenticatedTestClient(
        app,
        SUPPLIER_USER,
    ) as test_client:
        yield test_client


@pytest.fixture
def supplier_b_client():
    """
    TestClient authenticated as supplier SUP-00002.
    """

    with AuthenticatedTestClient(
        app,
        SUPPLIER_B_USER,
    ) as test_client:
        yield test_client


@pytest.fixture
def supplier_no_id_client():
    """
    TestClient authenticated as supplier without supplier_id.
    """

    with AuthenticatedTestClient(
        app,
        SUPPLIER_NO_ID_USER,
    ) as test_client:
        yield test_client


@pytest.fixture
def procurement_client():
    """
    TestClient authenticated as procurement manager.
    """

    with AuthenticatedTestClient(
        app,
        PROCUREMENT_USER,
    ) as test_client:
        yield test_client


@pytest.fixture
def compliance_client():
    """
    TestClient authenticated as compliance officer.
    """

    with AuthenticatedTestClient(
        app,
        COMPLIANCE_USER,
    ) as test_client:
        yield test_client



@pytest.fixture(autouse=True)
def compliance_db(tmp_path, monkeypatch):
    from app.services.supplier_compliance_service import (
        supplier_compliance_service,
    )

    monkeypatch.setattr(
        supplier_compliance_service,
        "_db_path",
        tmp_path / "compliance.db",
    )
    yield


@pytest.fixture
def po_db(monkeypatch):
    """
    In-memory SQLite database with the supplier_portal schema.

    Includes PO mirror and both outbox tables.
    All relevant service modules share the same test session factory.
    """
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.config import settings
    from app.database import Base
    from app.models.inventory_goods_receipt_event import (
        InventoryGoodsReceiptEvent,
    )
    from app.models.po_ack_outbox import POAckOutbox
    from app.models.po_mirror import POMirror
    from app.models.shipment_outbox import ShipmentOutbox
    from app.models.shipment_eta_event import ShipmentETAEvent

    schema_name = settings.SUPPLIER_DB_SCHEMA

    if not schema_name.replace("_", "").isalnum():
        raise ValueError(
            f"Unsupported SQLite schema name: {schema_name!r}"
        )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def attach_schema(dbapi_connection, _record):
        dbapi_connection.execute(
            f"ATTACH DATABASE ':memory:' AS {schema_name}"
        )

    Base.metadata.create_all(
        engine,
        tables=[
            POMirror.__table__,
            POAckOutbox.__table__,
            ShipmentOutbox.__table__,
            Shipment.__table__,
            ShipmentETAEvent.__table__,
            InventoryGoodsReceiptEvent.__table__,
        ],
    )

    factory = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    modules_to_patch = (
        "app.database",
        "app.graphql.queries",
        "app.graphql.mutations",
        "app.services.inventory_po_approved_consumer",
        "app.services.po_ack_outbox_publisher",
        "app.services.shipment_service",
        "app.services.shipment_outbox_publisher",
        "app.services.shipment_eta_consumer",
    )

    for module in modules_to_patch:
        monkeypatch.setattr(
            f"{module}.SessionLocal",
            factory,
        )

    yield factory

    engine.dispose()
