from app.schemas.shipment import (
    ShipmentCreate,
    Status,
    Carrier
)

from app.services.carriers.dhl import DHLAdapter
from app.services.carriers.fedex import FedExAdapter
from app.services.carriers.ups import UPSAdapter
from app.services.carriers.bluedart import BlueDartAdapter


# In-memory storage
shipments = {}


# Carrier Registry
CARRIERS = {
    Carrier.dhl: DHLAdapter(),
    Carrier.fedex: FedExAdapter(),
    Carrier.ups: UPSAdapter(),
    Carrier.bluedart: BlueDartAdapter()
}


# CREATE SHIPMENT
def create_shipment(shipment: ShipmentCreate):

    shipments[shipment.shipment_id] = shipment

    return shipment


# CHECK WHETHER SHIPMENT EXISTS
def shipment_exists(shipment_id: int):

    return shipment_id in shipments


# GET ALL SHIPMENTS
def get_all_shipments():

    return list(shipments.values())


# GET SHIPMENT BY ID
def get_shipment(shipment_id: int):

    return shipments.get(shipment_id)


# UPDATE SHIPMENT
def update_shipment(
    shipment_id: int,
    shipment: ShipmentCreate
):

    shipments[shipment_id] = shipment

    return shipment


# DELETE SHIPMENT
def delete_shipment(shipment_id: int):

    return shipments.pop(shipment_id, None)


# FILTER SHIPMENTS BY STATUS
def filter_shipments_by_status(status: Status):

    return [
        shipment
        for shipment in shipments.values()
        if shipment.status == status
    ]


# GET QUOTES
def get_quotes(
    origin: str,
    destination: str,
    weight_kg: float
):

    rates = []

    for adapter in CARRIERS.values():

        rate = adapter.get_rate(
            origin,
            destination,
            weight_kg
        )

        rates.append(rate)

    # Sort cheapest rate first
    rates.sort(
        key=lambda rate: rate.price
    )

    return rates