from app.core.database import SessionLocal
from app.services import audit_service
from app.services.audit_service import _build_audit_values


def test_build_audit_values_sets_clear_decision():
    result = _build_audit_values(
        entity_name="ACME LTD",
        result={
            "is_flagged": False,
            "match_score": 0,
        },
    )

    assert result["matched"] is False
    assert result["decision"] == "CLEAR"


def test_build_audit_values_sets_block_decision():
    result = _build_audit_values(
        entity_name="HAMAS TRADING",
        result={
            "is_flagged": True,
            "match_score": 95,
        },
    )

    assert result["matched"] is True
    assert result["decision"] == "BLOCK"


def test_build_audit_values_sets_review_decision():
    result = _build_audit_values(
        entity_name="REVIEW COMPANY",
        result={
            "is_flagged": True,
            "match_score": 85,
        },
    )

    assert result["matched"] is True
    assert result["decision"] == "REVIEW"


def test_build_audit_values_sets_block_decision_at_threshold():
    result = _build_audit_values(
        entity_name="THRESHOLD COMPANY",
        result={
            "is_flagged": True,
            "match_score": 90,
        },
    )

    assert result["matched"] is True
    assert result["decision"] == "BLOCK"


def test_audit_query_helpers_and_summary():
    db = SessionLocal()

    try:
        audit_service.write_audit(
            db,
            "  ACME LTD ",
            {"is_flagged": False, "match_score": 0, "country": "India"},
            duration_ms=10,
        )
        audit_service.write_audit(
            db,
            "acme ltd",
            {"is_flagged": True, "match_score": 95, "country": "India"},
            duration_ms=20,
            newly_flagged=True,
            screening_type="RESCREEN",
        )
        audit_service.write_audit(
            db,
            "CLEAR SUPPLIER",
            {"is_flagged": False, "match_score": 0, "country": "Canada"},
            duration_ms=5,
        )
        audit_service.write_audit(
            db,
            "",
            {"is_flagged": False, "match_score": 0},
            duration_ms=2,
        )

        all_audits = audit_service.get_all_audits(db)
        assert len(all_audits) == 4

        history = audit_service.get_audit_history(db, " ACME LTD ")
        assert len(history) == 2

        latest = audit_service.get_latest_audits(db)
        assert set(latest) == {"ACME LTD", "CLEAR SUPPLIER"}
        assert latest["ACME LTD"].matched is True

        cleared = audit_service.get_previously_cleared_entities(db)
        assert [record.entity_name for record in cleared] == ["CLEAR SUPPLIER"]

        summary = audit_service.get_audit_summary(db)
        assert summary["total_screenings"] == 4
        assert summary["total_flagged"] == 1
        assert summary["overall_flag_rate"] == 25.0
        assert summary["newly_flagged"] == 1
        assert summary["initial_screenings"] == 3
        assert summary["rescreenings"] == 1
        assert len(summary["flag_rate_over_time"]) == 1
        assert len(summary["country_summary"]) == 2

        audit_service.delete_all_audits(db)
        assert audit_service.get_all_audits(db) == []

        empty_summary = audit_service.get_audit_summary(db)
        assert empty_summary["total_screenings"] == 0
        assert empty_summary["overall_flag_rate"] == 0.0
        assert empty_summary["flag_rate_over_time"] == []
        assert empty_summary["country_summary"] == []

    finally:
        db.close()
