from datetime import datetime, UTC
import asyncio

from app.schemas.shipment import (
    ShipmentCreate,
    Status,
    Carrier,
    QuotePreference,
    QuoteRequest,
    QuoteResponse,
    CarrierRate,
    ShipmentEvent,
)

from app.services.carriers.dhl import DHLAdapter
from app.services.carriers.fedex import FedExAdapter
from app.services.carriers.ups import UPSAdapter
from app.services.carriers.bluedart import BlueDartAdapter


# ---------------- STORAGE ----------------

shipments: dict[int, ShipmentCreate] = {}
shipment_events: dict[int, list[ShipmentEvent]] = {}


# ---------------- CARRIERS ----------------

CARRIERS = {
    Carrier.dhl: DHLAdapter(),
    Carrier.fedex: FedExAdapter(),
    Carrier.ups: UPSAdapter(),
    Carrier.bluedart: BlueDartAdapter(),
}


# ---------------- STATUS TRANSITIONS ----------------

LEGAL_TRANSITIONS = {

    Status.pending: [
        Status.in_transit,
    ],

    Status.in_transit: [
        Status.delayed,
        Status.delivered,
    ],

    Status.delayed: [
        Status.in_transit,
        Status.delivered,
    ],

    Status.delivered: [],

    Status.cancelled: [],

}



# ---------------- EVENT MANAGEMENT ----------------


def event_location_for_status(
    status: Status,
    shipment: ShipmentCreate,
) -> str:

    if status == Status.delivered:
        return shipment.destination

    if status == Status.in_transit:
        return "In Transit"

    return shipment.origin



def record_event(
    shipment: ShipmentCreate,
):

    event = ShipmentEvent(

        shipment_id=shipment.shipment_id,

        status=shipment.status,

        timestamp=datetime.now(UTC),

        location=event_location_for_status(
            shipment.status,
            shipment,
        ),
    )


    shipment_events.setdefault(
        shipment.shipment_id,
        [],
    ).append(event)



def is_valid_transition(
    from_status: Status,
    to_status: Status,
) -> bool:

    return (

        from_status == to_status

        or

        to_status in LEGAL_TRANSITIONS.get(
            from_status,
            [],
        )

    )



# ---------------- SHIPMENT CRUD ----------------


def create_shipment(
    shipment: ShipmentCreate,
):

    shipments[shipment.shipment_id] = shipment

    record_event(shipment)

    return shipment



def shipment_exists(
    shipment_id: int,
):

    return shipment_id in shipments



def get_all_shipments():

    return list(
        shipments.values()
    )



def get_shipment(
    shipment_id: int,
):

    return shipments.get(
        shipment_id
    )



def update_shipment(
    shipment_id: int,
    shipment: ShipmentCreate,
):

    existing_shipment = get_shipment(
        shipment_id
    )


    if existing_shipment is None:

        return None



    if not is_valid_transition(
        existing_shipment.status,
        shipment.status,
    ):

        raise ValueError(

            f"Invalid status transition: "

            f"{existing_shipment.status} -> "

            f"{shipment.status}"

        )



    shipments[shipment_id] = shipment



    if shipment.status != existing_shipment.status:

        record_event(shipment)



    return shipment



def delete_shipment(
    shipment_id: int,
):

    shipment_events.pop(
        shipment_id,
        None,
    )


    return shipments.pop(
        shipment_id,
        None,
    )



def filter_shipments_by_status(
    status: Status,
):

    return [

        shipment

        for shipment in shipments.values()

        if shipment.status == status

    ]



# ---------------- QUOTE MANAGEMENT ----------------


def sort_rates(
    rates: list[CarrierRate],
    preference: QuotePreference,
) -> list[CarrierRate]:


    if preference == QuotePreference.cheapest:

        return sorted(
            rates,
            key=lambda rate: rate.price,
        )



    if preference == QuotePreference.fastest:

        return sorted(
            rates,
            key=lambda rate: rate.estimated_days,
        )



    if preference == QuotePreference.most_reliable:

        return sorted(

            rates,

            key=lambda rate: (

                rate.reliability_score * 100

                - rate.price * 0.01

                - rate.estimated_days

            ),

            reverse=True,

        )


    return rates



def get_quote_response(
    origin: str,
    destination: str,
    weight_kg: float,
    preference: QuotePreference = QuotePreference.cheapest,
) -> QuoteResponse:


    rates = []

    warnings = []


    for adapter in CARRIERS.values():


        try:

            rate = adapter.get_rate(

                origin,

                destination,

                weight_kg,

            )

            rates.append(rate)



        except Exception:


            carrier_name = (

                adapter.__class__.__name__

                .replace(
                    "Adapter",
                    ""
                )

            )


            warnings.append(

                f"{carrier_name} unavailable"

            )



    rates = sort_rates(
        rates,
        preference,
    )


    return QuoteResponse(

        rates=rates,

        warnings=warnings,

    )



def get_quotes(
    origin: str,
    destination: str,
    weight_kg: float,
    preference: QuotePreference = QuotePreference.cheapest,
):

    return get_quote_response(

        origin,

        destination,

        weight_kg,

        preference,

    )



# ---------------- BULK QUOTES ----------------


async def get_bulk_quotes(
    requests: list[QuoteRequest],
) -> list[QuoteResponse]:


    loop = asyncio.get_running_loop()


    tasks = [

        loop.run_in_executor(

            None,

            get_quote_response,

            request.origin,

            request.destination,

            request.weight_kg,

            request.preference,

        )

        for request in requests

    ]


    return await asyncio.gather(
        *tasks
    )



# ---------------- HISTORY ----------------


def get_shipment_history(
    shipment_id: int,
) -> list[ShipmentEvent]:


    return sorted(

        shipment_events.get(

            shipment_id,

            [],

        ),

        key=lambda event: event.timestamp,

    )