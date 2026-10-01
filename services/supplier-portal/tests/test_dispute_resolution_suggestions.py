import pytest

from app.services.three_way_match_service import (
    three_way_matches,
)


# ============================================================
# HELPERS
# ============================================================

def seed_match(
    match_id: str,
    supplier_id: str,
    invoice_number: str,
    status: str,
    discrepancies: list[str],
    resolution_reason: str | None = None,
):
    three_way_matches[
        (supplier_id, invoice_number)
    ] = {
        "match_id": match_id,
        "supplier_id": supplier_id,
        "invoice_number": invoice_number,
        "status": status,
        "lines": [],
        "discrepancies": discrepancies,
        "created_at": None,
        "created_by": "test@example.com",
        "resolution": (
            {
                "reason": resolution_reason,
                "resolved_at": None,
                "resolved_by": "compliance@example.com",
                "resolved_role": "compliance_officer",
            }
            if resolution_reason
            else None
        ),
        "resolved_at": None,
        "resolved_by": None,
        "payment_approved": False,
        "payment_approved_at": None,
        "payment_approved_by": None,
        "payment_approved_role": None,
    }


@pytest.fixture(autouse=True)
def reset_matches():
    three_way_matches.clear()

    yield

    three_way_matches.clear()


# ============================================================
# SERVICE TESTS
# ============================================================

def test_price_mismatch_suggests_correct_invoice():
    """
    Historical price-mismatch cases mostly resulted
    in corrected invoices.
    """

    seed_match(
        match_id="HIST-001",
        supplier_id="SUP001",
        invoice_number="OLD001",
        status="matched",
        discrepancies=["price_mismatch"],
        resolution_reason="Corrected invoice received from supplier.",
    )

    seed_match(
        match_id="HIST-002",
        supplier_id="SUP002",
        invoice_number="OLD002",
        status="matched",
        discrepancies=["price_mismatch"],
        resolution_reason="Invoice correction requested.",
    )

    seed_match(
        match_id="HIST-003",
        supplier_id="SUP003",
        invoice_number="OLD003",
        status="matched",
        discrepancies=["price_mismatch"],
        resolution_reason="Credit note issued.",
    )

    seed_match(
        match_id="CURRENT-001",
        supplier_id="SUP001",
        invoice_number="INV1001",
        status="discrepancy",
        discrepancies=["price_mismatch"],
    )

    from app.services.dispute_resolution_service import (
        get_dispute_resolution_suggestions,
    )

    result = get_dispute_resolution_suggestions(
        supplier_id="SUP001",
        invoice_number="INV1001",
    )

    assert result["match_id"] == "CURRENT-001"
    assert len(result["suggestions"]) == 1

    suggestion = result["suggestions"][0]

    assert suggestion["discrepancy_type"] == "price_mismatch"
    assert suggestion["suggested_action"] == "correct_invoice"
    assert suggestion["historical_case_count"] == 3
    assert suggestion["supporting_case_count"] == 2


def test_quantity_mismatch_suggests_credit_note():
    """
    Historical quantity-mismatch cases mostly resulted
    in credit notes.
    """

    seed_match(
        match_id="HIST-004",
        supplier_id="SUP001",
        invoice_number="OLD004",
        status="matched",
        discrepancies=["quantity_mismatch"],
        resolution_reason="Credit note issued for excess quantity.",
    )

    seed_match(
        match_id="HIST-005",
        supplier_id="SUP002",
        invoice_number="OLD005",
        status="matched",
        discrepancies=["quantity_mismatch"],
        resolution_reason="Credit memo issued.",
    )

    seed_match(
        match_id="HIST-006",
        supplier_id="SUP003",
        invoice_number="OLD006",
        status="matched",
        discrepancies=["quantity_mismatch"],
        resolution_reason="Manual compliance review completed.",
    )

    seed_match(
        match_id="CURRENT-002",
        supplier_id="SUP001",
        invoice_number="INV1002",
        status="discrepancy",
        discrepancies=["quantity_mismatch"],
    )

    from app.services.dispute_resolution_service import (
        get_dispute_resolution_suggestions,
    )

    result = get_dispute_resolution_suggestions(
        supplier_id="SUP001",
        invoice_number="INV1002",
    )

    suggestion = result["suggestions"][0]

    assert suggestion["discrepancy_type"] == "quantity_mismatch"
    assert suggestion["suggested_action"] == "credit_note"
    assert suggestion["historical_case_count"] == 3
    assert suggestion["supporting_case_count"] == 2


def test_multiple_discrepancies_generate_multiple_suggestions():
    """
    A dispute containing both quantity and price mismatches
    receives one suggestion for each discrepancy type.
    """

    seed_match(
        match_id="HIST-007",
        supplier_id="SUP001",
        invoice_number="OLD007",
        status="matched",
        discrepancies=["quantity_mismatch"],
        resolution_reason="Credit note issued.",
    )

    seed_match(
        match_id="HIST-008",
        supplier_id="SUP002",
        invoice_number="OLD008",
        status="matched",
        discrepancies=["price_mismatch"],
        resolution_reason="Corrected invoice received.",
    )

    seed_match(
        match_id="CURRENT-003",
        supplier_id="SUP001",
        invoice_number="INV1003",
        status="discrepancy",
        discrepancies=[
            "quantity_mismatch",
            "price_mismatch",
        ],
    )

    from app.services.dispute_resolution_service import (
        get_dispute_resolution_suggestions,
    )

    result = get_dispute_resolution_suggestions(
        supplier_id="SUP001",
        invoice_number="INV1003",
    )

    assert len(result["suggestions"]) == 2

    suggestions = {
        item["discrepancy_type"]: item
        for item in result["suggestions"]
    }

    assert (
        suggestions["quantity_mismatch"]["suggested_action"]
        == "credit_note"
    )

    assert (
        suggestions["price_mismatch"]["suggested_action"]
        == "correct_invoice"
    )


def test_no_historical_cases_returns_no_suggestion():
    """
    The system should not invent a recommendation when
    there is no historical evidence.
    """

    seed_match(
        match_id="CURRENT-004",
        supplier_id="SUP001",
        invoice_number="INV1004",
        status="discrepancy",
        discrepancies=["price_mismatch"],
    )

    from app.services.dispute_resolution_service import (
        get_dispute_resolution_suggestions,
    )

    result = get_dispute_resolution_suggestions(
        supplier_id="SUP001",
        invoice_number="INV1004",
    )

    suggestion = result["suggestions"][0]

    assert suggestion["suggested_action"] is None
    assert suggestion["historical_case_count"] == 0
    assert suggestion["supporting_case_count"] == 0


def test_unresolved_historical_cases_are_ignored():
    """
    Historical disputes that are still unresolved must not
    be used as evidence.
    """

    seed_match(
        match_id="HIST-009",
        supplier_id="SUP001",
        invoice_number="OLD009",
        status="discrepancy",
        discrepancies=["price_mismatch"],
        resolution_reason=None,
    )

    seed_match(
        match_id="CURRENT-005",
        supplier_id="SUP001",
        invoice_number="INV1005",
        status="discrepancy",
        discrepancies=["price_mismatch"],
    )

    from app.services.dispute_resolution_service import (
        get_dispute_resolution_suggestions,
    )

    result = get_dispute_resolution_suggestions(
        supplier_id="SUP001",
        invoice_number="INV1005",
    )

    suggestion = result["suggestions"][0]

    assert suggestion["suggested_action"] is None
    assert suggestion["historical_case_count"] == 0


def test_current_match_is_not_used_as_historical_evidence():
    """
    The current dispute must never be counted as its own
    historical evidence.
    """

    seed_match(
        match_id="CURRENT-006",
        supplier_id="SUP001",
        invoice_number="INV1006",
        status="discrepancy",
        discrepancies=["price_mismatch"],
        resolution_reason="Corrected invoice received.",
    )

    from app.services.dispute_resolution_service import (
        get_dispute_resolution_suggestions,
    )

    result = get_dispute_resolution_suggestions(
        supplier_id="SUP001",
        invoice_number="INV1006",
    )

    suggestion = result["suggestions"][0]

    assert suggestion["suggested_action"] is None
    assert suggestion["historical_case_count"] == 0


def test_unclassified_resolution_is_ignored():
    """
    A historical resolution reason that cannot be classified
    should not produce an unsupported suggestion.
    """

    seed_match(
        match_id="HIST-010",
        supplier_id="SUP001",
        invoice_number="OLD010",
        status="matched",
        discrepancies=["price_mismatch"],
        resolution_reason="Issue discussed with supplier.",
    )

    seed_match(
        match_id="CURRENT-007",
        supplier_id="SUP001",
        invoice_number="INV1007",
        status="discrepancy",
        discrepancies=["price_mismatch"],
    )

    from app.services.dispute_resolution_service import (
        get_dispute_resolution_suggestions,
    )

    result = get_dispute_resolution_suggestions(
        supplier_id="SUP001",
        invoice_number="INV1007",
    )

    suggestion = result["suggestions"][0]

    assert suggestion["suggested_action"] is None
    assert suggestion["historical_case_count"] == 0


def test_resolved_current_match_cannot_generate_suggestion():
    """
    Suggestions are only for unresolved discrepancies.
    """

    seed_match(
        match_id="CURRENT-008",
        supplier_id="SUP001",
        invoice_number="INV1008",
        status="matched",
        discrepancies=["price_mismatch"],
        resolution_reason="Corrected invoice received.",
    )

    from app.services.dispute_resolution_service import (
        get_dispute_resolution_suggestions,
    )

    with pytest.raises(ValueError, match="unresolved discrepancies"):
        get_dispute_resolution_suggestions(
            supplier_id="SUP001",
            invoice_number="INV1008",
        )


def test_unknown_match_raises_error():
    """
    Unknown match should return a service-level not-found error.
    """

    from app.services.dispute_resolution_service import (
        get_dispute_resolution_suggestions,
    )

    with pytest.raises(
        KeyError,
        match="Three-way match not found",
    ):
        get_dispute_resolution_suggestions(
            supplier_id="SUP001",
            invoice_number="UNKNOWN",
        )


def test_suggestion_service_is_read_only():
    """
    Generating a suggestion must not modify the current
    three-way match.
    """

    seed_match(
        match_id="CURRENT-009",
        supplier_id="SUP001",
        invoice_number="INV1009",
        status="discrepancy",
        discrepancies=["price_mismatch"],
    )

    from app.services.dispute_resolution_service import (
        get_dispute_resolution_suggestions,
    )

    before = dict(
        three_way_matches[
            ("SUP001", "INV1009")
        ]
    )

    get_dispute_resolution_suggestions(
        supplier_id="SUP001",
        invoice_number="INV1009",
    )

    after = three_way_matches[
        ("SUP001", "INV1009")
    ]

    assert after == before