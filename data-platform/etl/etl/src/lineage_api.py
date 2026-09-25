
from flask import Flask, jsonify

from config_loader import load_pipeline_config
from database import get_engine
from lineage import trace_row_lineage

app = Flask(__name__)


@app.route("/lineage/row/<int:row_id>", methods=["GET"])
def get_sales_lineage(row_id):
    return get_table_lineage("sales_fact", row_id)


@app.route("/lineage/<table_name>/row/<int:row_id>", methods=["GET"])
def get_table_lineage(table_name, row_id):
    try:
        lineage = trace_row_lineage(
            row_id,
            table_name,
            config=load_pipeline_config(),
            engine=get_engine(),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not lineage:
        return jsonify({"error": "Row not found"}), 404

    return jsonify({
        "target_table": table_name,
        "target_row_id": row_id,
        "lineage": lineage,
    })


if __name__ == "__main__":
    app.run(debug=False, port=5002)
