from pydantic import BaseModel


class InventoryValueReportItem(BaseModel):

    warehouse_id: str

    category: str

    inventory_value: float


class InventoryValueReportResponse(BaseModel):

    valuation_method: str

    report: list[InventoryValueReportItem]

    total_inventory_value: float