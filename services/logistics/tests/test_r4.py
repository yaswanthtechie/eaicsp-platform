import asyncio

import pytest

from app.schemas.shipment import (
    Carrier,
    QuotePreference,
    QuoteRequest,
    ShipmentCreate,
    Status,
)

from app.services.shipment_service import (
    shipments,
    shipment_events,
    carrier_history,
    CIRCUIT_BREAKERS,
    calculate_reliability_score,
    get_reliability_score,
    record_carrier_result,
    reset_all_circuit_breakers,
    reset_circuit_breaker,
    is_circuit_open,
    is_valid_transition,
    get_consolidation_suggestions,
    explain_eta,
    get_bulk_quotes,
)


# ============================================================
# TEST SETUP
# ============================================================

def setup_function():
    shipments.clear()
    shipment_events.clear()
    reset_all_circuit_breakers()


# ============================================================
# R4 - 1
# REAL ASYNC BULK QUOTING
# ============================================================

@pytest.mark.asyncio
async def test_r4_bulk_quote_parallel():
    requests = [
        QuoteRequest(
            origin="Hyderabad",
            destination="Mumbai",
            weight_kg=10,
            preference=QuotePreference.cheapest,
        ),
        QuoteRequest(
            origin="Hyderabad",
            destination="Delhi",
            weight_kg=15,
            preference=QuotePreference.fastest,
        ),
        QuoteRequest(
            origin="Hyderabad",
            destination="Bangalore",
            weight_kg=5,
            preference=QuotePreference.most_reliable,
        ),
    ]

    result = await get_bulk_quotes(
        requests,
        benchmark=False,
    )

    assert "quotes" in result
    assert "performance" in result

    assert len(result["quotes"]) == 3

    performance = result["performance"]

    assert performance["shipment_count"] == 3
    assert performance["parallel_seconds"] >= 0


# ============================================================
# R4 - 1
# BENCHMARK
# ============================================================

@pytest.mark.asyncio
async def test_r4_bulk_quote_benchmark():
    requests = [
        QuoteRequest(
            origin="Hyderabad",
            destination="Mumbai",
            weight_kg=10,
            preference=QuotePreference.cheapest,
        ),
        QuoteRequest(
            origin="Hyderabad",
            destination="Delhi",
            weight_kg=10,
            preference=QuotePreference.fastest,
        ),
    ]

    result = await get_bulk_quotes(
        requests,
        benchmark=True,
    )

    assert "quotes" in result
    assert "performance" in result

    performance = result["performance"]

    assert performance["shipment_count"] == 2

    assert performance["parallel_seconds"] >= 0

    assert (
        performance["sequential_seconds"]
        is not None
    )

    assert (
        performance["speedup"]
        is not None
    )


# ============================================================
# R4 - 1
# MAXIMUM 20 SHIPMENTS
# ============================================================

@pytest.mark.asyncio
async def test_r4_bulk_quote_20_shipments():
    requests = []

    for _ in range(20):
        requests.append(
            QuoteRequest(
                origin="Hyderabad",
                destination="Mumbai",
                weight_kg=5,
                preference=QuotePreference.cheapest,
            )
        )

    result = await get_bulk_quotes(
        requests,
        benchmark=False,
    )

    assert len(result["quotes"]) == 20


# ============================================================
# R4 - 2
# DYNAMIC RELIABILITY SCORE
# ============================================================

def test_r4_reliability_score():
    history = [
        True,
        True,
        True,
        False,
        True,
    ]

    score = calculate_reliability_score(
        history
    )

    assert score == 0.8


# ============================================================
# R4 - 2
# RECORD CARRIER RESULT
# ============================================================

def test_r4_record_carrier_result():
    carrier = Carrier.dhl

    old_length = len(
        carrier_history[carrier]
    )

    record_carrier_result(
        carrier,
        True,
    )

    new_length = len(
        carrier_history[carrier]
    )

    assert new_length == old_length + 1


# ============================================================
# R4 - 2
# GET RELIABILITY SCORE
# ============================================================

def test_r4_get_reliability_score():
    carrier_history[Carrier.ups] = [
        True,
        True,
        False,
        True,
    ]

    score = get_reliability_score(
        Carrier.ups
    )

    assert score == 0.75


# ============================================================
# R4 - 3
# CONSOLIDATION SUGGESTIONS
# ============================================================

def test_r4_consolidation_same_destination():
    shipment1 = ShipmentCreate(
        shipment_id=101,
        origin="Hyderabad",
        destination="Mumbai",
        carrier=Carrier.dhl,
        status=Status.pending,
        estimated_delivery=date_for_test(
            "2026-08-20"
        ),
        weight_kg=10,
    )

    shipment2 = ShipmentCreate(
        shipment_id=102,
        origin="Hyderabad",
        destination="Mumbai",
        carrier=Carrier.ups,
        status=Status.pending,
        estimated_delivery=date_for_test(
            "2026-08-21"
        ),
        weight_kg=15,
    )

    shipments[101] = shipment1
    shipments[102] = shipment2

    suggestions = (
        get_consolidation_suggestions()
    )

    assert len(suggestions) >= 1

    found = False

    for suggestion in suggestions:

        shipment_ids = (
            suggestion["shipment_ids"]
        )

        if (
            101 in shipment_ids
            and 102 in shipment_ids
        ):
            found = True
            break

    assert found is True


# ============================================================
# R4 - 3
# NO CONSOLIDATION FOR DIFFERENT DESTINATION
# ============================================================

def test_r4_no_consolidation_different_destination():
    shipment1 = ShipmentCreate(
        shipment_id=103,
        origin="Hyderabad",
        destination="Mumbai",
        carrier=Carrier.dhl,
        status=Status.pending,
        estimated_delivery=date_for_test(
            "2026-08-20"
        ),
        weight_kg=10,
    )

    shipment2 = ShipmentCreate(
        shipment_id=104,
        origin="Hyderabad",
        destination="Delhi",
        carrier=Carrier.dhl,
        status=Status.pending,
        estimated_delivery=date_for_test(
            "2026-08-21"
        ),
        weight_kg=10,
    )

    shipments[103] = shipment1
    shipments[104] = shipment2

    suggestions = (
        get_consolidation_suggestions()
    )

    for suggestion in suggestions:

        shipment_ids = (
            suggestion["shipment_ids"]
        )

        assert not (
            103 in shipment_ids
            and 104 in shipment_ids
        )


# ============================================================
# R4 - 4
# CIRCUIT BREAKER RESET
# ============================================================

def test_r4_reset_single_circuit_breaker():
    carrier = Carrier.dhl

    breaker = CIRCUIT_BREAKERS[
        carrier
    ]

    breaker.failure_count = 3
    breaker.state = "OPEN"

    assert is_circuit_open(
        carrier
    ) is True

    reset_circuit_breaker(
        carrier
    )

    assert is_circuit_open(
        carrier
    ) is False

    assert breaker.failure_count == 0


# ============================================================
# R4 - 4
# RESET ALL CIRCUIT BREAKERS
# ============================================================

def test_r4_reset_all_circuit_breakers():
    for breaker in CIRCUIT_BREAKERS.values():
        breaker.failure_count = 3
        breaker.state = "OPEN"

    reset_all_circuit_breakers()

    for carrier in Carrier:

        assert (
            is_circuit_open(carrier)
            is False
        )

        assert (
            CIRCUIT_BREAKERS[
                carrier
            ].failure_count
            == 0
        )


# ============================================================
# R4 - 4
# CIRCUIT BREAKER OPENS AFTER 3 FAILURES
# ============================================================

def test_r4_circuit_breaker_opens_after_three_failures():
    carrier = Carrier.fedex

    breaker = CIRCUIT_BREAKERS[
        carrier
    ]

    breaker.record_failure()

    assert is_circuit_open(
        carrier
    ) is False

    breaker.record_failure()

    assert is_circuit_open(
        carrier
    ) is False

    breaker.record_failure()

    assert is_circuit_open(
        carrier
    ) is True


# ============================================================
# R4 - 5
# STATUS TRANSITION
# ============================================================

def test_r4_valid_status_transitions():

    assert is_valid_transition(
        Status.pending,
        Status.in_transit,
    )

    assert is_valid_transition(
        Status.in_transit,
        Status.delayed,
    )

    assert is_valid_transition(
        Status.in_transit,
        Status.delivered,
    )

    assert is_valid_transition(
        Status.delayed,
        Status.in_transit,
    )

    assert is_valid_transition(
        Status.delayed,
        Status.delivered,
    )


# ============================================================
# R4 - 5
# INVALID STATUS TRANSITIONS
# ============================================================

def test_r4_invalid_status_transitions():

    assert not is_valid_transition(
        Status.pending,
        Status.delivered,
    )

    assert not is_valid_transition(
        Status.pending,
        Status.delayed,
    )

    assert not is_valid_transition(
        Status.delivered,
        Status.in_transit,
    )

    assert not is_valid_transition(
        Status.cancelled,
        Status.in_transit,
    )


# ============================================================
# R4 - 6
# ETA EXPLANATION
# ============================================================

def test_r4_eta_explanation():

    shipment = ShipmentCreate(
        shipment_id=200,
        origin="Hyderabad",
        destination="Mumbai",
        carrier=Carrier.dhl,
        status=Status.pending,
        estimated_delivery=date_for_test(
            "2026-08-20"
        ),
        weight_kg=10,
    )

    shipments[200] = shipment

    result = explain_eta(
        200
    )

    assert result["shipment_id"] == 200

    assert (
        result["origin"]
        == "Hyderabad"
    )

    assert (
        result["destination"]
        == "Mumbai"
    )

    assert (
        result["carrier"]
        == "dhl"
    )

    assert (
        result["distance_km"]
        > 0
    )

    assert (
        result["reliability_score"]
        >= 0
    )

    assert (
        "explanation"
        in result
    )


# ============================================================
# R4 - 6
# ETA UNKNOWN SHIPMENT
# ============================================================

def test_r4_eta_unknown_shipment():

    with pytest.raises(
        ValueError,
        match="Shipment not found",
    ):
        explain_eta(
            99999
        )


# ============================================================
# HELPER
# ============================================================

def date_for_test(value: str):
    from datetime import date

    year, month, day = map(
        int,
        value.split("-"),
    )

    return date(
        year,
        month,
        day,
    )