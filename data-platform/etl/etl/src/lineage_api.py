from flask import Flask, jsonify
from sqlalchemy import text

from database import get_engine

app = Flask(__name__)

engine = get_engine()


@app.route("/lineage/row/<int:row_id>", methods=["GET"])
def get_lineage(row_id):

    query = text("""
        SELECT
            sf.id,
            sf.date,
            sf.sku_id,
            sf.warehouse_id,
            sf.quantity_sold,
            sf.unit_price,
            sf.source_batch,
            sf.loaded_at,
            sf.updated_at,
            sf.run_id,
            sf.pipeline_version,

            erl.pipeline_name,
            erl.started_at,
            erl.finished_at,
            erl.status,
            erl.batches_seen,
            erl.rows_inserted,
            erl.rows_updated,
            erl.rows_rejected,
            erl.error_message

        FROM sales_fact sf

        LEFT JOIN etl_run_log erl
        ON sf.run_id = erl.run_id

        WHERE sf.id = :row_id;
    """)

    with engine.connect() as connection:

        result = connection.execute(
            query,
            {
                "row_id": row_id
            }
        ).mappings().first()

    if result is None:

        return jsonify(
            {
                "error": "Row not found"
            }
        ), 404

    return jsonify(dict(result))


if __name__ == "__main__":

    app.run(
        debug=True,
        port=5002
    )