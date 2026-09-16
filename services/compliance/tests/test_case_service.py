import pytest

from app.core.database import SessionLocal
from app.models.case_history import CaseHistory
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

def test_case_deduplication_reuses_same_entity_and_country():
    db = SessionLocal()

    result = {
        "matched_name": "ABC COMPANY",
        "matched_lists": ["OFAC"],
        "match_score": 100,
        "risk_score": 80.0,
        "screening_tier": "HIGH",
        "screening_action": "ENHANCED_REVIEW_AND_MANUAL_APPROVAL",
    }

    try:
        first_case = create_case(
            db=db,
            entity_name="ABC COMPANY",
            entity_type="supplier",
            country="India",
            result=result,
        )

        second_case = create_case(
            db=db,
            entity_name="  abc   company  ",
            entity_type="supplier",
            country="india",
            result=result,
        )

        assert second_case.id == first_case.id
        assert second_case.case_number == first_case.case_number

    finally:
        db.close()


def test_case_deduplication_does_not_reuse_case_for_different_country():
    db = SessionLocal()

    result = {
        "matched_name": "ABC COMPANY",
        "matched_lists": ["OFAC"],
        "match_score": 100,
        "risk_score": 80.0,
        "screening_tier": "HIGH",
        "screening_action": "ENHANCED_REVIEW_AND_MANUAL_APPROVAL",
    }

    try:
        india_case = create_case(
            db=db,
            entity_name="ABC COMPANY",
            entity_type="supplier",
            country="India",
            result=result,
        )

        usa_case = create_case(
            db=db,
            entity_name="ABC COMPANY",
            entity_type="supplier",
            country="USA",
            result=result,
        )

        assert usa_case.id != india_case.id
        assert usa_case.country == "USA"

    finally:
        db.close()


def test_case_deduplication_does_not_treat_sql_wildcards_as_wildcards():
    db = SessionLocal()

    result = {
        "matched_name": "ABC COMPANY",
        "matched_lists": ["OFAC"],
        "match_score": 100,
        "risk_score": 80.0,
        "screening_tier": "HIGH",
        "screening_action": "ENHANCED_REVIEW_AND_MANUAL_APPROVAL",
    }

    try:
        first_case = create_case(
            db=db,
            entity_name="ABC%COMPANY",
            entity_type="supplier",
            country="India",
            result=result,
        )

        second_case = create_case(
            db=db,
            entity_name="ABCXCOMPANY",
            entity_type="supplier",
            country="India",
            result=result,
        )

        assert second_case.id != first_case.id

    finally:
        db.close()

def test_case_number_matches_database_id():
    db = SessionLocal()

    try:
        case = create_test_case(db)

        assert case.id is not None
        assert case.case_number == f"CASE-{case.id:06d}"

    finally:
        db.close()

def test_different_cases_have_unique_case_numbers():
    db = SessionLocal()

    result = {
        "matched_name": "TEST ENTITY",
        "matched_lists": ["OFAC"],
        "match_score": 100,
        "risk_score": 80.0,
        "screening_tier": "HIGH",
        "screening_action": "ENHANCED_REVIEW_AND_MANUAL_APPROVAL",
    }

    try:
        first_case = create_case(
            db=db,
            entity_name="TEST ENTITY ONE",
            entity_type="supplier",
            country="India",
            result=result,
        )

        second_case = create_case(
            db=db,
            entity_name="TEST ENTITY TWO",
            entity_type="supplier",
            country="India",
            result=result,
        )

        assert first_case.id != second_case.id
        assert first_case.case_number != second_case.case_number
        assert first_case.case_number == f"CASE-{first_case.id:06d}"
        assert second_case.case_number == f"CASE-{second_case.id:06d}"

    finally:
        db.close()