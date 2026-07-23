from app.schemas.shipment import ShipmentCreate, Status
#memory store

from app.services.carriers.dhl import DHLAdapter
from app.services.carriers.fedex import FedExAdapter
from app.services.carriers.ups import UPSAdapter
from app.services.carriers.bluedart import BlueDartAdapter

shipments = {}


def create_shipment(shipment: ShipmentCreate):
    shipments[shipment.shipment_id] = shipment
    return shipment


def shipment_exists(shipment_id: int):
    return shipment_id in shipments


def get_all_shipments():
    return list(shipments.values())


def get_shipment(shipment_id: int):
    return shipments.get(shipment_id)


def update_shipment(shipment_id: int, shipment: ShipmentCreate):
    shipments[shipment_id] = shipment
    return shipment


def delete_shipment(shipment_id: int):
    return shipments.pop(shipment_id, None)


def filter_shipments_by_status(status: Status):
    return [
        shipment
        for shipment in shipments.values()
        if shipment.status == status
    ]

def get_quotes(origin,destination,weight_kg):
    dhl=DHLAdapter()
    fedex=FedExAdapter()
    ups=UPSAdapter()
    bluedart=BlueDartAdapter()
    #get rates
    dhl_rate=dhl.get_rate(
        origin,destination,weight_kg
    )
    fedex_rate=fedex.get_rate(
        origin,destination,weight_kg
    )
    ups_rate=ups.get_rate(
        origin,destination,weight_kg
    )
    bluedart_rate=bluedart.get_rate(
        origin,destination,weight_kg)
    rates=[dhl_rate,fedex_rate,ups_rate,bluedart_rate]
    rates.sort(
        key=lambda rate:rate["price"]
    )
    return rates