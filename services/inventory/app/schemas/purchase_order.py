from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PurchaseOrderRequest(BaseModel):
    sku_id: str
    warehouse_id: str


class PurchaseOrderResponse(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    po_id: str
    sku_id: str
    warehouse_id: str
    supplier_id: str
    quantity: int
    unit_cost: float
    expected_cost: float
    status: str
    created_at: datetime