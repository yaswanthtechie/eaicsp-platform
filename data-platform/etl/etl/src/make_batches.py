import pandas as pd
import random
from datetime import date, timedelta
from pathlib import Path

batch_folder = Path("data/batches")
batch_folder.mkdir(parents=True, exist_ok=True)

start_date = date(2024, 1, 1)

for day_offset in range(5):

    current_date = start_date + timedelta(days=day_offset)

    sales_data = []

    for _ in range(400):

        record = {
            "date": current_date.isoformat(),
            "sku_id": f"SKU{random.randint(100, 999)}",
            "warehouse_id": f"WH{random.randint(1, 5)}",
            "quantity_sold": random.randint(1, 20),
            "unit_price": random.randint(100, 1000)
        }

        sales_data.append(record)

    df = pd.DataFrame(sales_data)

    file_name = batch_folder / f"sales_{current_date}.csv"

    df.to_csv(file_name, index=False)