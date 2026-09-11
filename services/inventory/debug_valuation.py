from app.database import SessionLocal
from app.services.valuation_service import (
    calculate_weighted_average_value,
)


db = SessionLocal()

try:

    value = calculate_weighted_average_value(
        db=db,
        sku_id="SKU0021",
        warehouse_id="WH001",
    )

    print("Weighted Average Value:", value)

finally:

    db.close()