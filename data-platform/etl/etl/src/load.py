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
            updated_at = NOW()
        RETURNING (xmax = 0) AS inserted;
    """)

    rows_inserted = 0
    rows_updated = 0

    with engine.begin() as connection:

        for batch in validated_data_frames:

            df = batch["data"]

            source_batch = str(batch["file_path"].name)

            records = df.to_dict(orient="records")

            for record in records:
                record["source_batch"] = source_batch

            result = connection.execute(upsert_query, records)

            for row in result:
                if row.inserted:
                    rows_inserted += 1
                else:
                    rows_updated += 1

    print(
        f"Data loaded successfully! "
        f"Inserted: {rows_inserted}, Updated: {rows_updated}"
    )

    return rows_inserted, rows_updated