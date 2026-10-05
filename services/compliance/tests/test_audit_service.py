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