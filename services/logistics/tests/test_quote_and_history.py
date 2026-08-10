import pytest
from datetime import date

from app.services.shipment_service import (
    CARRIERS,
    create_shipment,
    get_quotes,
    get_shipment_history,
    shipment_exists,
    update_shipment,
    shipments,
    shipment_events,
)

from app.schemas.shipment import (
    ShipmentCreate,
    Status,
    Carrier,
    QuotePreference,
)

from app.services.carriers.fedex import FedExAdapter

from app.services.carriers.base import (
    api_retry,
    CarrierError,
)


# -----------------------------------------
# Clear data before every test
# -----------------------------------------

@pytest.fixture(autouse=True)
def clear_storage():

    shipments.clear()
    shipment_events.clear()

    yield

    shipments.clear()
    shipment_events.clear()



# -----------------------------------------
# Helper function
# -----------------------------------------

def create_test_shipment(
    shipment_id,
    status=Status.pending
):

    return ShipmentCreate(

        shipment_id=shipment_id,

        origin="Hyderabad",

        destination="Mumbai",

        carrier=Carrier.dhl,

        status=status,

        estimated_delivery=date(
            2027,
            1,
            1
        ),

        weight_kg=12.5
    )



# -----------------------------------------
# Carrier failure warning test
# -----------------------------------------

def test_quote_returns_warnings_on_carrier_failure(
    monkeypatch
):

    fedex = FedExAdapter()


    def failed_rate(
        origin,
        destination,
        weight_kg
    ):

        raise CarrierError(
            "FedEx API timeout"
        )


    monkeypatch.setattr(
        fedex,
        "get_rate",
        failed_rate
    )


    old_fedex = CARRIERS[Carrier.fedex]


    CARRIERS[Carrier.fedex] = fedex


    try:

        quote = get_quotes(
            "Hyderabad",
            "Mumbai",
            10.0,
            QuotePreference.cheapest
        )


        assert any(
            "FedEx unavailable" in warning
            for warning in quote.warnings
        )


        assert len(quote.rates) > 0


    finally:

        CARRIERS[Carrier.fedex] = old_fedex




# -----------------------------------------
# Fastest preference
# -----------------------------------------

def test_quote_preference_fastest():

    quote = get_quotes(
        "Hyderabad",
        "Mumbai",
        10.0,
        QuotePreference.fastest
    )


    assert quote.rates


    assert (
        quote.rates[0].estimated_days
        <=
        quote.rates[-1].estimated_days
    )



# -----------------------------------------
# Most reliable preference
# -----------------------------------------

def test_quote_preference_most_reliable():

    quote = get_quotes(
        "Hyderabad",
        "Mumbai",
        10.0,
        QuotePreference.most_reliable
    )


    assert quote.rates


    assert (
        quote.rates[0].reliability_score
        >=
        quote.rates[-1].reliability_score
    )



# -----------------------------------------
# Shipment history test
# pending -> in_transit
# -----------------------------------------

def test_shipment_history_records_transitions():


    shipment = create_test_shipment(
        1001,
        Status.pending
    )


    create_shipment(
        shipment
    )


    assert shipment_exists(1001)



    updated = create_test_shipment(
        1001,
        Status.in_transit
    )


    update_shipment(
        1001,
        updated
    )


    history = get_shipment_history(
        1001
    )


    assert len(history) == 2


    assert history[0].status == Status.pending

    assert history[1].status == Status.in_transit




# -----------------------------------------
# Illegal transition
# delivered -> pending
# -----------------------------------------

def test_illegal_transition_delivered_to_pending():


    create_shipment(
        create_test_shipment(
            1002,
            Status.pending
        )
    )


    update_shipment(
        1002,
        create_test_shipment(
            1002,
            Status.in_transit
        )
    )


    update_shipment(
        1002,
        create_test_shipment(
            1002,
            Status.delivered
        )
    )


    with pytest.raises(
        ValueError
    ):

        update_shipment(
            1002,
            create_test_shipment(
                1002,
                Status.pending
            )
        )



# -----------------------------------------
# Retry mechanism test
# -----------------------------------------

def test_retry_is_triggered_three_times():


    counter = {
        "calls": 0
    }



    @api_retry()
    def failing_api():


        counter["calls"] += 1


        raise CarrierError(
            "Temporary carrier failure"
        )



    with pytest.raises(
        CarrierError
    ):

        failing_api()



    assert counter["calls"] == 3