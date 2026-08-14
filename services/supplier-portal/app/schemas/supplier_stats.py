from pydantic import BaseModel


class SupplierStatsResponse(BaseModel):
    supplier_id: str
    po_count: int
    on_time_percentage: float
    average_invoice_cycle_time: float