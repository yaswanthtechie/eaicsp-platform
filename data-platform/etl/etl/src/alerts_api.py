from datetime import datetime, timedelta
import os

from flask import Flask, jsonify, request
from sqlalchemy import text

from database import get_engine

app = Flask(__name__)



@app.get("/alerts")
def get_alerts():

    engine = get_engine()

    since = request.args.get("since", "1h")

    if since.endswith("h"):
        hours = int(since[:-1])
        threshold = datetime.now() - timedelta(hours=hours)

    elif since.endswith("m"):
        minutes = int(since[:-1])
        threshold = datetime.now() - timedelta(minutes=minutes)

    else:
        return jsonify(
            {"error": "Use format like 10m or 1h"}
        ), 400

    query = text("""
        SELECT
            alert_id,
            pipeline,
            severity,
            message,
            batch_file,
            run_id,
            created_at
        FROM etl_alerts
        WHERE created_at >= :threshold
        ORDER BY created_at DESC
    """)

    with engine.connect() as conn:

        rows = conn.execute(
            query,
            {"threshold": threshold}
        )

        alerts = [
            dict(row._mapping)
            for row in rows
        ]

    return jsonify(alerts)


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")