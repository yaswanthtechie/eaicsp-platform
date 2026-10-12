from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from app.schemas.events import (
    SupplierComplianceStatus,
    SupplierStatusChangedEvent,
)
from app.services.supplier_compliance_service import (
    ComplianceDatabaseError,
    SupplierComplianceService,
)
from app.services.supplier_onboarding_service import suppliers


@pytest.fixture
def compliance_db(tmp_path):
    """Create an isolated SQLite database and supplier for each test."""
    suppliers.clear()
    suppliers["SUP001"] = {
        "supplier_id": "SUP001",
        "company_name": "ABC Supplies",
        "contact_name": "Supplier User",
        "email": "supplier@company.com",
        "country": "India",
        "status": "active",
    }

    db_path = tmp_path / "compliance_state.db"
    service = SupplierComplianceService(db_path=db_path)

    yield service, db_path

    suppliers.clear()


def make_event(
    event_id="event-001",
    new_status="BLOCK",
    occurred_at=None,
):
    """Build a valid compliance status-changed event."""
    if occurred_at is None:
        occurred_at = datetime.now(timezone.utc)

    return SupplierStatusChangedEvent.model_validate({
        "event_id": event_id,
        "event_type": "compliance.supplier.status_changed",
        "event_version": 1,
        "occurred_at": occurred_at.isoformat(),
        "producer": "compliance-service",
        "payload": {
            "supplier_name": "ABC Supplies",
            "country": "India",
            "old_status": "CLEAR",
            "new_status": new_status,
            "matched_list": ["test-watchlist"],
            "reason": "Test compliance decision",
            "screening_run_id": f"screen-{event_id}",
        },
    })


def test_block_status_survives_service_restart(compliance_db):
    service, db_path = compliance_db
    event = make_event(new_status="BLOCK")

    assert service.apply_status_changed_event(
        event, supplier_id="SUP001"
    ) is True

    # Simulate a service restart by creating a new service instance.
    restarted_service = SupplierComplianceService(db_path=db_path)

    assert (
        restarted_service.get_access_status("SUP001")
        == SupplierComplianceStatus.suspended
    )
    assert restarted_service.is_event_processed(event.event_id) is True
    assert len(restarted_service.get_audit_history("SUP001")) == 1


def test_duplicate_event_does_not_create_duplicate_audit(compliance_db):
    service, _ = compliance_db
    event = make_event(event_id="duplicate-001", new_status="BLOCK")

    assert service.apply_status_changed_event(
        event, supplier_id="SUP001"
    ) is True

    assert service.apply_status_changed_event(
        event, supplier_id="SUP001"
    ) is False

    assert len(service.get_audit_history("SUP001")) == 1
    assert service.get_access_status("SUP001") == (
        SupplierComplianceStatus.suspended
    )


def test_stale_event_is_recorded_but_does_not_change_status(compliance_db):
    service, _ = compliance_db
    now = datetime.now(timezone.utc)

    newer_block = make_event(
        event_id="newer-block",
        new_status="BLOCK",
        occurred_at=now,
    )
    older_review = make_event(
        event_id="older-review",
        new_status="REVIEW",
        occurred_at=now - timedelta(minutes=5),
    )

    assert service.apply_status_changed_event(
        newer_block, supplier_id="SUP001"
    ) is True

    assert service.apply_status_changed_event(
        older_review, supplier_id="SUP001"
    ) is False

    assert service.is_event_processed("older-review") is True
    assert service.get_access_status("SUP001") == (
        SupplierComplianceStatus.suspended
    )

    # Only the applied event should appear in the audit history.
    assert len(service.get_audit_history("SUP001")) == 1


def test_audit_failure_rolls_back_state_and_processed_event(compliance_db):
    service, db_path = compliance_db
    event = make_event(event_id="rollback-001", new_status="BLOCK")

    # Initialize the schema before installing the failure trigger.
    with service._connect() as conn:
        conn.execute("""
            CREATE TRIGGER fail_compliance_audit_insert
            BEFORE INSERT ON compliance_audit
            BEGIN
                SELECT RAISE(ABORT, 'simulated audit write failure');
            END;
        """)

    with pytest.raises(ComplianceDatabaseError):
        service.apply_status_changed_event(
            event, supplier_id="SUP001"
        )

    # Verify directly in SQLite that the whole transaction rolled back.
    with sqlite3.connect(str(db_path)) as conn:
        state = conn.execute(
            """
            SELECT status
            FROM supplier_compliance_state
            WHERE supplier_key = ?
            """,
            ("SUP001",),
        ).fetchone()

        processed = conn.execute(
            """
            SELECT event_id
            FROM processed_events
            WHERE event_id = ?
            """,
            (event.event_id,),
        ).fetchone()

        audit = conn.execute(
            """
            SELECT event_id
            FROM compliance_audit
            WHERE event_id = ?
            """,
            (event.event_id,),
        ).fetchone()

    assert state is None
    assert processed is None
    assert audit is None

    # No durable BLOCK state was committed.
    assert service.get_access_status("SUP001") == (
        SupplierComplianceStatus.cleared
    )
