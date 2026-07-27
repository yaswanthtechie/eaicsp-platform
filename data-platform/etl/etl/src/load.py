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
            unit_price,
            source_batch
        )
        VALUES (
            :date,
            :sku_id,
            :warehouse_id,
            :quantity_sold,
            :unit_price,
            :source_batch
        )
        ON CONFLICT (date, sku_id, warehouse_id)
        DO UPDATE SET
            quantity_sold = EXCLUDED.quantity_sold,
            unit_price = EXCLUDED.unit_price,
            source_batch = EXCLUDED.source_batch,
            updated_at = NOW();
    """)

    with engine.begin() as connection:

        for batch in validated_data_frames:

            df = batch["data"]

            source_batch = batch["file_path"]

            records = df.to_dict(orient="records")

            for record in records:
                record["source_batch"] = source_batch

            connection.execute(upsert_query, records)

    print("Data loaded successfully!")