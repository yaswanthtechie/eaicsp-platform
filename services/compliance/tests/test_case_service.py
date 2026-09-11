import pytest

from app.core.database import SessionLocal
from app.models.case_history import CaseHistory
from app.models.compliance_case import ComplianceCase
from app.services.case_service import (
    assign_case,
    create_case,
    transition_case,
)


def create_test_case(db):
    result = {
        "matched_name": "HAMAS",
        "matched_lists": ["OFAC", "EU"],
        "match_score": 100,
        "risk_score": 66.0,
        "screening_tier": "MEDIUM",
        "screening_action": "ADDITIONAL_COMPLIANCE_REVIEW",
    }

    return create_case(
        db=db,
        entity_name="HAMAS",
        entity_type="supplier",
        country="India",
        result=result,
    )


def test_flagged_entity_creates_open_case():

    db = SessionLocal()

    try:
        case = create_test_case(db)

        assert case.id is not None
        assert case.case_number == "CASE-000001"
        assert case.entity_name == "HAMAS"
        assert case.status == "OPEN"

    finally:
        db.close()


def test_case_creation_creates_history():

    db = SessionLocal()

    try:
        case = create_test_case(db)

        history = (
            db.query(CaseHistory)
            .filter(
                CaseHistory.case_id == case.id
            )
            .all()
        )

        assert len(history) == 1
        assert history[0].from_status is None
        assert history[0].to_status == "OPEN"
        assert history[0].changed_by == "system"

    finally:
        db.close()


def test_case_can_move_to_under_review():

    db = SessionLocal()

    try:
        case = create_test_case(db)

        transition_case(
            db=db,
            case=case,
            new_status="UNDER_REVIEW",
            changed_by="compliance_officer",
        )

        assert case.status == "UNDER_REVIEW"

    finally:
        db.close()


def test_case_can_be_cleared():

    db = SessionLocal()

    try:
        case = create_test_case(db)

        transition_case(
            db=db,
            case=case,
            new_status="UNDER_REVIEW",
            changed_by="compliance_officer",
        )

        transition_case(
            db=db,
            case=case,
            new_status="CLEARED",
            changed_by="compliance_officer",
            reason="False positive after compliance review",
            comments="Entity does not match the sanctioned party.",
        )

        assert case.status == "CLEARED"
        assert case.resolution == "CLEARED"
        assert case.resolution_reason == (
            "False positive after compliance review"
        )
        assert case.resolved_at is not None

    finally:
        db.close()


def test_case_can_be_confirmed():

    db = SessionLocal()

    try:
        case = create_test_case(db)

        transition_case(
            db=db,
            case=case,
            new_status="UNDER_REVIEW",
            changed_by="compliance_officer",
        )

        transition_case(
            db=db,
            case=case,
            new_status="CONFIRMED",
            changed_by="compliance_officer",
            reason="Sanctions match confirmed",
        )

        assert case.status == "CONFIRMED"
        assert case.resolution == "CONFIRMED"
        assert case.resolution_reason == (
            "Sanctions match confirmed"
        )
        assert case.resolved_at is not None

    finally:
        db.close()


def test_invalid_open_to_cleared_transition():

    db = SessionLocal()

    try:
        case = create_test_case(db)

        with pytest.raises(ValueError):
            transition_case(
                db=db,
                case=case,
                new_status="CLEARED",
                changed_by="compliance_officer",
            )

        assert case.status == "OPEN"

    finally:
        db.close()


def test_case_can_be_assigned():

    db = SessionLocal()

    try:
        case = create_test_case(db)

        assign_case(
            db=db,
            case=case,
            assigned_to="compliance_officer",
            changed_by="admin",
        )

        assert case.assigned_to == "compliance_officer"
        assert case.assigned_at is not None

    finally:
        db.close()


def test_case_history_contains_full_resolution_trail():

    db = SessionLocal()

    try:
        case = create_test_case(db)

        transition_case(
            db=db,
            case=case,
            new_status="UNDER_REVIEW",
            changed_by="compliance_officer",
        )

        transition_case(
            db=db,
            case=case,
            new_status="CLEARED",
            changed_by="compliance_officer",
            reason="False positive",
        )

        history = (
            db.query(CaseHistory)
            .filter(
                CaseHistory.case_id == case.id
            )
            .order_by(CaseHistory.id)
            .all()
        )

        assert len(history) == 3

        assert history[0].to_status == "OPEN"

        assert history[1].from_status == "OPEN"
        assert history[1].to_status == "UNDER_REVIEW"

        assert history[2].from_status == "UNDER_REVIEW"
        assert history[2].to_status == "CLEARED"

        assert history[2].reason == "False positive"

    finally:
        db.close()