from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.models.po_ack_outbox import POAckOutbox
from app.models.po_mirror import POMirror
from app.services.po_acknowledgement_service import (
    POAcknowledgementError,
    acknowledge_approved_po,
)
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

def make_po(
    *,
    po_id="PO-2026-000123",
    supplier_id="SUP-00045",
    status="approved",
):
    return SimpleNamespace(
        po_id=po_id,
        po_number="PO-NUM-123",
        supplier_id=supplier_id,
        warehouse_id="WH-BLR-01",
        status=status,
        acknowledged_at=None,
    )


@pytest.fixture
def mock_db():
    db = MagicMock()
    query = MagicMock()

    db.query.return_value = query
    query.filter.return_value = query
    query.with_for_update.return_value = query

    return db, query


def test_acknowledge_approved_po_updates_status_and_timestamp(
    mock_db,
):
    db, query = mock_db
    po = make_po()
    query.one_or_none.return_value = po

    result = acknowledge_approved_po(
        db=db,
        po_id=po.po_id,
        supplier_id=po.supplier_id,
    )

    assert result is po
    assert po.status == "acknowledged"
    assert po.acknowledged_at is not None
    assert po.acknowledged_at.tzinfo is not None

    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(po)
    db.rollback.assert_not_called()


def test_acknowledgement_creates_correct_outbox_event(
    mock_db,
):
    db, query = mock_db
    po = make_po()
    query.one_or_none.return_value = po

    acknowledge_approved_po(
        db=db,
        po_id=po.po_id,
        supplier_id=po.supplier_id,
    )

    outbox = db.add.call_args.args[0]

    assert isinstance(outbox, POAckOutbox)
    assert outbox.topic == settings.PO_ACKNOWLEDGED_TOPIC
    assert outbox.message_key == po.po_id
    assert outbox.status == "pending"
    assert outbox.attempts == 0

    payload = outbox.payload

    assert payload["event_type"] == "supplierportal.po.acknowledged"
    assert payload["event_version"] == 1
    assert payload["producer"] == "supplier-portal"
    assert payload["payload"]["po_number"] == po.po_id
    assert payload["payload"]["supplier_id"] == po.supplier_id
    assert payload["payload"]["acknowledged_at"] is not None
    assert payload["event_id"] == outbox.event_id
    assert payload["occurred_at"] is not None


def test_missing_or_other_supplier_po_returns_none(
    mock_db,
):
    db, query = mock_db
    query.one_or_none.return_value = None

    result = acknowledge_approved_po(
        db=db,
        po_id="PO-2026-000123",
        supplier_id="SUP-99999",
    )

    assert result is None
    db.rollback.assert_called_once()
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_repeated_acknowledgement_does_not_create_another_event(
    mock_db,
):
    db, query = mock_db
    po = make_po(status="acknowledged")
    existing_timestamp = datetime.now(timezone.utc)
    po.acknowledged_at = existing_timestamp
    query.one_or_none.return_value = po

    result = acknowledge_approved_po(
        db=db,
        po_id=po.po_id,
        supplier_id=po.supplier_id,
    )

    assert result is po
    assert po.status == "acknowledged"
    assert po.acknowledged_at == existing_timestamp

    db.add.assert_not_called()
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_invalid_po_status_raises_error_and_rolls_back(
    mock_db,
):
    db, query = mock_db
    po = make_po(status="cancelled")
    query.one_or_none.return_value = po

    with pytest.raises(
        POAcknowledgementError,
        match="cannot be acknowledged",
    ):
        acknowledge_approved_po(
            db=db,
            po_id=po.po_id,
            supplier_id=po.supplier_id,
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_commit_failure_rolls_back_and_reraises(
    mock_db,
):
    db, query = mock_db
    po = make_po()
    query.one_or_none.return_value = po
    db.commit.side_effect = RuntimeError("database commit failed")

    with pytest.raises(
        RuntimeError,
        match="database commit failed",
    ):
        acknowledge_approved_po(
            db=db,
            po_id=po.po_id,
            supplier_id=po.supplier_id,
        )

    assert po.status == "acknowledged"
    db.add.assert_called_once()
    db.rollback.assert_called_once()
    db.refresh.assert_not_called()


def test_query_is_locked_and_scoped_to_requested_po_and_supplier(
    mock_db,
):
    db, query = mock_db
    query.one_or_none.return_value = None

    acknowledge_approved_po(
        db=db,
        po_id="PO-2026-000123",
        supplier_id="SUP-00045",
    )

    db.query.assert_called_once_with(POMirror)
    query.filter.assert_called_once()
    query.with_for_update.assert_called_once()
    query.one_or_none.assert_called_once()

ACK_CONTRACT = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "events"
    / "supplierportal.po.acknowledged.v1.json"
)


@pytest.mark.parametrize("po_number", ["PO-NUM-123", None])
def test_outbox_payload_matches_acknowledged_contract(
    mock_db,
    po_number,
):
    """The event we store must be exactly what the contract allows."""
    db, query = mock_db
    po = make_po()
    po.po_number = po_number
    query.one_or_none.return_value = po

    acknowledge_approved_po(
        db=db,
        po_id=po.po_id,
        supplier_id=po.supplier_id,
    )

    event = db.add.call_args.args[0].payload
    schema = json.loads(ACK_CONTRACT.read_text(encoding="utf-8-sig"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    errors = [error.message for error in validator.iter_errors(event)]
    assert errors == []

