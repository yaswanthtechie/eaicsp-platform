from fastapi import APIRouter
from typing import Optional

from app.schemas.shipment import ShipmentCreate, Status

from app.services.shipment_service import (
    create_shipment,
    get_all_shipments,
    get_shipment,
    update_shipment,
    delete_shipment,
    filter_shipments_by_status,
    shipment_exists,
    get_quotes
)

from app.services.carriers.dhl import DHLAdapter
from app.services.carriers.fedex import FedExAdapter
from app.services.carriers.ups import UPSAdapter
from app.services.carriers.bluedart import BlueDartAdapter


router = APIRouter(
    prefix="/api/v1/shipments",
    tags=["Shipments"]
)

#create shipment
@router.post("/")
def create_new_shipment(data: ShipmentCreate):

    if shipment_exists(data.shipment_id):
        return{
        "message":"Shipment already exists"
        }

    return create_shipment(data)

#get all shipment
@router.get("/")
def get_shipments(
    status: Optional[Status] = None
):

    if status:
        return filter_shipments_by_status(status)

    return get_all_shipments()

#get shipment by id
@router.get("/{shipment_id}")
def get_one_shipment(shipment_id: int):

    shipment = get_shipment(shipment_id)

    if shipment is None:
        return{
            "message":"Shipment not found"
        }
    return shipment

#update shipment
@router.put("/{shipment_id}")
def update_existing_shipment(
    shipment_id: int,
    data: ShipmentCreate
):

    shipment=get_shipment(shipment_id)
    if shipment is None:
        return{
            "message":"Shipment not found"
        }
    return update_shipment(shipment_id, data)

#delete shipment
@router.delete("/{shipment_id}")
def delete_existing_shipment(shipment_id: int):

    shipment = delete_shipment(shipment_id)

    if shipment is None:
        return{
             "message":"Shipment not found"
        }

    return {
        "message": "Shipment deleted successfully"
    }

#track shipment
@router.get("/{shipment_id}/tracking")
def track_shipment(shipment_id: int):

    shipment = get_shipment(shipment_id)

    if shipment is None:
        return{
            "message":"Shipment not found"
        }
    

    if shipment.carrier == "dhl":
        adapter = DHLAdapter()

    elif shipment.carrier == "fedex":
        adapter = FedExAdapter()

    elif shipment.carrier == "ups":
        adapter = UPSAdapter()
    
    elif shipment.carrier =="bluedart":
        adapter = BlueDartAdapter()

    else:
        return{
            "message":"Unsupported carrier"
        }
    return adapter.get_tracking(shipment_id)


#get quote
@router.post("/quote")
def shipment_quote(
    origin:str,
    destination:str,
    weight_kg:float
):
    return get_quotes(
        origin,destination,weight_kg
    )
