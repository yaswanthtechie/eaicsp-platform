from sqlalchemy import text
from database import get_engine


def load_data(validated_data_frames):

    engine = get_engine()

    upsert_query = text("""
        INSERT INTO sales_fact (
            date,
            sku_id,
            warehouse_id,
            quantity_sold,
            unit_price
        )
        VALUES (
            :date,
            :sku_id,
            :warehouse_id,
            :quantity_sold,
            :unit_price
        )
        ON CONFLICT (date, sku_id, warehouse_id)
        DO UPDATE SET
            quantity_sold = EXCLUDED.quantity_sold,
            unit_price = EXCLUDED.unit_price;
    """)

    with engine.begin() as connection:

        for df in validated_data_frames:

            records = df.to_dict(orient="records")

            connection.execute(upsert_query, records)

    print("Data loaded successfully!")