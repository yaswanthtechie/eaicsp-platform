from datetime import date

import pytest

from app.schemas.shipment import (
    ShipmentCreate,
    Status,
    Carrier,
)

from app.services import shipment_service


def make_shipment(
    shipment_id=1,
    status=Status.pending,
    carrier=Carrier.dhl,
):

    return ShipmentCreate(
        shipment_id=shipment_id,
        origin="Hyderabad",
        destination="Mumbai",
        carrier=carrier,
        status=status,
        estimated_delivery=date(
            2026,
            8,
            20,
        ),
        weight_kg=5,
    )


# ============================================================
# VALID TRANSITIONS
# ============================================================

def test_pending_to_in_transit():

    assert shipment_service.is_valid_transition(
        Status.pending,
        Status.in_transit,
    )


def test_in_transit_to_delivered():

    assert shipment_service.is_valid_transition(
        Status.in_transit,
        Status.delivered,
    )


def test_in_transit_to_delayed():

    assert shipment_service.is_valid_transition(
        Status.in_transit,
        Status.delayed,
    )


def test_delayed_to_delivered():

    assert shipment_service.is_valid_transition(
        Status.delayed,
        Status.delivered,
    )


# ============================================================
# INVALID TRANSITIONS
# ============================================================

def test_pending_to_delivered_invalid():

    assert not shipment_service.is_valid_transition(
        Status.pending,
        Status.delivered,
    )


def test_delivered_to_in_transit_invalid():

    assert not shipment_service.is_valid_transition(
        Status.delivered,
        Status.in_transit,
    )


def test_cancelled_to_in_transit_invalid():

    assert not shipment_service.is_valid_transition(
        Status.cancelled,
        Status.in_transit,
    )


# ============================================================
# SHIPMENT UPDATE
# ============================================================

def test_update_invalid_transition():

    shipment_service.shipments.clear()
    shipment_service.shipment_events.clear()

    shipment = make_shipment()

    shipment_service.create_shipment(
        shipment
    )

    delivered = make_shipment(
        status=Status.delivered
    )

    with pytest.raises(ValueError):

        shipment_service.update_shipment(
            1,
            delivered,
        )


# ============================================================
# RELIABILITY
# ============================================================

def test_dynamic_reliability():

    original = (
        shipment_service.carrier_history[
            Carrier.dhl
        ]
    )

    try:

        shipment_service.carrier_history[
            Carrier.dhl
        ] = [
            True,
            True,
            True,
            False,
        ]

        score = (
            shipment_service
            .get_reliability_score(
                Carrier.dhl
            )
        )

        assert score == 0.75

    finally:

        shipment_service.carrier_history[
            Carrier.dhl
        ] = original