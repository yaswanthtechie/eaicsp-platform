import asyncio
from datetime import date

from app.schemas.shipment import (
    QuoteRequest,
    QuotePreference,
    Carrier,
    Status,
    ShipmentCreate,
)

from app.services import shipment_service


# ============================================================
# BULK REQUEST
# ============================================================

def create_quote_requests(
    count=20,
):

    return [

        QuoteRequest(
            origin="Hyderabad",
            destination="Mumbai",
            weight_kg=5,
            preference=(
                QuotePreference.cheapest
            ),
        )

        for _ in range(count)
    ]


# ============================================================
# 20 SHIPMENT BULK TEST
# ============================================================

def test_bulk_quote_supports_20_shipments():

    requests = create_quote_requests(
        20
    )

    result = asyncio.run(
        shipment_service.get_bulk_quotes(
            requests
        )
    )

    assert len(
        result["quotes"]
    ) == 20

    assert (
        result["performance"][
            "shipment_count"
        ]
        == 20
    )


# ============================================================
# PARALLEL SPEEDUP TEST
# ============================================================

def test_parallel_bulk_is_faster():

    requests = create_quote_requests(
        20
    )

    result = asyncio.run(
        shipment_service.get_bulk_quotes(
            requests
        )
    )

    performance = result[
        "performance"
    ]

    assert (
        performance[
            "parallel_seconds"
        ]
        < performance[
            "sequential_seconds"
        ]
    )

    assert (
        performance["speedup"]
        > 1
    )


# ============================================================
# TWO OF FOUR CARRIERS DOWN
# ============================================================

def test_two_carriers_down():

    original_carriers = (
        shipment_service.CARRIERS.copy()
    )

    class FailingAdapter:

        def get_rate(
            self,
            origin,
            destination,
            weight_kg,
        ):

            raise Exception(
                "Mock carrier failure"
            )

        def get_tracking(
            self,
            tracking_number,
        ):

            raise Exception(
                "Mock tracking failure"
            )

    try:

        shipment_service.CARRIERS[
            Carrier.dhl
        ] = FailingAdapter()

        shipment_service.CARRIERS[
            Carrier.fedex
        ] = FailingAdapter()

        shipment_service.reset_all_circuit_breakers()

        result = (
            shipment_service
            .get_quote_response_sequential(
                "Hyderabad",
                "Mumbai",
                5,
            )
        )

        carriers = [
            rate.carrier
            for rate in result.rates
        ]

        assert (
            Carrier.ups
            in carriers
        )

        assert (
            Carrier.bluedart
            in carriers
        )

    finally:

        shipment_service.CARRIERS.clear()

        shipment_service.CARRIERS.update(
            original_carriers
        )

        shipment_service.reset_all_circuit_breakers()


# ============================================================
# CIRCUIT BREAKER
# ============================================================

def test_circuit_breaker_opens():

    original_carriers = (
        shipment_service.CARRIERS.copy()
    )

    class AlwaysFailAdapter:

        def get_rate(
            self,
            origin,
            destination,
            weight_kg,
        ):

            raise Exception(
                "Carrier permanently down"
            )

        def get_tracking(
            self,
            tracking_number,
        ):

            raise Exception(
                "Carrier permanently down"
            )

    try:

        shipment_service.CARRIERS[
            Carrier.dhl
        ] = AlwaysFailAdapter()

        shipment_service.reset_circuit_breaker(
            Carrier.dhl
        )

        # Failure 1
        shipment_service.call_one_carrier(
            Carrier.dhl,
            "Hyderabad",
            "Mumbai",
            5,
        )

        # Failure 2
        shipment_service.call_one_carrier(
            Carrier.dhl,
            "Hyderabad",
            "Mumbai",
            5,
        )

        # Failure 3
        shipment_service.call_one_carrier(
            Carrier.dhl,
            "Hyderabad",
            "Mumbai",
            5,
        )

        assert (
            shipment_service.is_circuit_open(
                Carrier.dhl
            )
        )

        # Fourth call should not hit adapter.
        rate, warning = (
            shipment_service.call_one_carrier(
                Carrier.dhl,
                "Hyderabad",
                "Mumbai",
                5,
            )
        )

        assert rate is None

        assert (
            "circuit is OPEN"
            in warning
        )

    finally:

        shipment_service.CARRIERS.clear()

        shipment_service.CARRIERS.update(
            original_carriers
        )

        shipment_service.reset_all_circuit_breakers()


# ============================================================
# CONSOLIDATION
# ============================================================

def test_consolidation_suggestion():

    shipment_service.shipments.clear()
    shipment_service.shipment_events.clear()

    shipment_service.create_shipment(
        ShipmentCreate(
            shipment_id=101,
            origin="Hyderabad",
            destination="Mumbai",
            carrier=Carrier.dhl,
            status=Status.pending,
            estimated_delivery=date(
                2026,
                8,
                20,
            ),
            weight_kg=5,
        )
    )

    shipment_service.create_shipment(
        ShipmentCreate(
            shipment_id=102,
            origin="Hyderabad",
            destination="Mumbai",
            carrier=Carrier.ups,
            status=Status.pending,
            estimated_delivery=date(
                2026,
                8,
                21,
            ),
            weight_kg=10,
        )
    )

    suggestions = (
        shipment_service
        .get_consolidation_suggestions()
    )

    assert len(
        suggestions
    ) >= 1

    assert (
        suggestions[0][
            "destination"
        ]
        == "Mumbai"
    )


# ============================================================
# ETA EXPLANATION
# ============================================================

def test_eta_explanation():

    shipment_service.shipments.clear()
    shipment_service.shipment_events.clear()

    shipment_service.create_shipment(
        ShipmentCreate(
            shipment_id=200,
            origin="Hyderabad",
            destination="Mumbai",
            carrier=Carrier.dhl,
            status=Status.pending,
            estimated_delivery=date(
                2026,
                8,
                20,
            ),
            weight_kg=5,
        )
    )

    result = (
        shipment_service.explain_eta(
            200
        )
    )

    assert result is not None

    assert (
        result["shipment_id"]
        == 200
    )

    assert (
        "explanation"
        in result
    )