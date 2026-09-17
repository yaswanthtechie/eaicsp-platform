from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.database import get_db

from app.schemas.inventory_report import (
    InventoryValueReportResponse,
)

from app.services.inventory_report_service import (
    generate_inventory_value_report,
)


router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
)


@router.get(
    "/inventory-value",
    response_model=InventoryValueReportResponse,
)
async def inventory_value_report(

    valuation_method: Literal[
        "fifo",
        "weighted_average",
    ] = "fifo",

    db: Session = Depends(get_db),

    auth=Depends(
        require_roles(
            "analyst",
            "warehouse_manager",
            "procurement_manager",
            "logistics_manager",
            "compliance_officer",
            "vp_operations",
            "ceo",
        )
    ),
):

    try:

        return generate_inventory_value_report(
            db=db,
            valuation_method=valuation_method,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )