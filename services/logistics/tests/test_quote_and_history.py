import pytest
from app.services.shipment_service import (
    CARRIERS,
    create_shipment,
    get_quotes,
    get_shipment_history,
    get_shipment,
    shipment_exists,
)
from app.schemas.shipment import (
    ShipmentCreate,
    Status,
    Carrier,
    QuoteRequest,
    QuotePreference,
)
from app.services.carriers.fedex import FedExAdapter


def test_quote_returns_warnings_on_carrier_failure(monkeypatch):
    fedex = FedExAdapter()

    # Force FedEx to fail all retry attempts.
    monkeypatch.setattr(fedex, "get_rate", lambda origin, destination, weight_kg: (_ for _ in ()).throw(RuntimeError("FedEx API timeout")))
    CARRIERS[Carrier.fedex] = fedex

    quote = get_quotes("Hyderabad", "Mumbai", 10.0, QuotePreference.cheapest)

    assert any("FedEx unavailable" in warning for warning in quote.warnings)
    assert quote.rates


def test_quote_preference_fastest():
    quote = get_quotes("Hyderabad", "Mumbai", 10.0, QuotePreference.fastest)

    assert quote.rates[0].estimated_days <= quote.rates[1].estimated_days


def test_quote_preference_most_reliable():
    quote = get_quotes("Hyderabad", "Mumbai", 10.0, QuotePreference.most_reliable)

    assert quote.rates[0].reliability_score >= quote.rates[-1].reliability_score


def test_shipment_history_records_transitions():
    shipment = ShipmentCreate(
        shipment_id=100,
        origin="Hyderabad",
        destination="Mumbai",
        carrier=Carrier.dhl,
        status=Status.pending,
        estimated_delivery="2027-01-01",
        weight_kg=12.5,
    )

    create_shipment(shipment)
    assert shipment_exists(100)

    shipment.status = Status.in_transit
    create_shipment(shipment)

    history = get_shipment_history(100)
    assert len(history) >= 2
    assert history[0].status == Status.pending
    assert history[1].status == Status.in_transit
